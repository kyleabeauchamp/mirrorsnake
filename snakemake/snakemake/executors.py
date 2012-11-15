
import os, time, textwrap, stat, shutil, random, string, threading
import concurrent.futures
from functools import partial
from itertools import chain

from snakemake.shell import shell
from snakemake.logging import logger
from snakemake.utils import format
from snakemake.exceptions import print_exception, get_exception_origin, format_error, RuleException, ClusterJobException, ProtectedOutputException
	
class AbstractExecutor:

	def __init__(self, workflow, dag, printreason = False, quiet = False, printshellcmds = False, printthreads = True):
		self.workflow = workflow
		self.dag = dag
		self.quiet = quiet
		self.printreason = printreason
		self.printshellcmds = printshellcmds
		self.printthreads = printthreads

	def run(self, job, callback = None, error_callback = None):
		self._run(job)
		callback(job)

	def shutdown(self):
		pass
	
	def _run(self, job):
		if job.message:
			logger.info(job.message)
		else:
			self.dag.printjob(job, 
			                  quiet=self.quiet, 
			                  printreason=self.printreason, 
			                  printshellcmds=self.printshellcmds, 
			                  printthreads=self.printthreads)
	
	def finish_job(self, job):
		self.dag.check_output(job)
		self.dag.handle_protected(job)
		self.dag.handle_temp(job)

class TouchExecutor(AbstractExecutor):

	def run(self, job, callback = None, error_callback = None):
		super()._run(job)
		try:
			for f in job.expanded_output:
				f.touch()
			time.sleep(0.1)
			callback(job)
		except OSError as ex:
			print_exception(ex, self.workflow.linemaps)
			error_callback()

class CPUExecutor(AbstractExecutor):

	def __init__(self, workflow, dag, cores, printreason=False, quiet=False, printshellcmds=False, threads=False):
		super().__init__(workflow, dag, printreason=printreason, quiet=quiet, printshellcmds=printshellcmds)
		self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=cores) if threads else concurrent.futures.ProcessPoolExecutor(max_workers=cores)

	def run(self, job, callback = None, error_callback = None):
		super()._run(job)
		
		job.prepare()
		
		future = self.pool.submit(run_wrapper, job.rule.run_func, job.input, job.output, job.wildcards, job.threads, job.log, self.workflow.linemaps)
		future.add_done_callback(partial(self._callback, job, callback, error_callback))
	
	def shutdown(self):
		self.pool.shutdown()
	
	def _callback(self, job, callback, error_callback, future):
		try:
			ex = future.exception()
			if ex:
				raise ex
			self.finish_job(job)
			callback(job)
		except (Exception, BaseException) as ex:
			print_exception(ex, self.workflow.linemaps)
			job.cleanup()
			error_callback()
			
class ClusterExecutor(AbstractExecutor):

	def __init__(self, workflow, dag, cores, submitcmd="qsub", printreason=False, quiet=False, printshellcmds=False):
		super().__init__(workflow, dag, printreason=printreason, quiet=quiet, printshellcmds=printshellcmds)
		if workflow.snakemakepath is None:
			raise ValueError("Cluster executor needs to know the path to the snakemake binary.")
		self.submitcmd = submitcmd
		self.startedjobs = 0
		self._tmpdir = None
		self.cores = cores if cores else ""
	
	def shutdown(self):
		shutil.rmtree(self.tmpdir)
	
	def run(self, job, callback = None, error_callback = None):
		super()._run(job)
		workdir = os.getcwd()
		jobid = self.startedjobs
		
		jobscript = os.path.join(self.tmpdir, "{}.sh".format(jobid))
		jobfinished = os.path.join(self.tmpdir, "{}.jobfinished".format(jobid))
		jobfailed = os.path.join(self.tmpdir, "{}.jobfailed".format(jobid))
		with open(jobscript, "w") as f:
			print(format(textwrap.dedent("""
			                                       #!/bin/sh
			                                       #rule: {job}
			                                       #input: {job.input}
			                                       #output: {job.output}
			                                       {self.workflow.snakemakepath} --force -j{self.cores} --directory {workdir} --nocolor --quiet {job.output} && touch "{jobfinished}" || touch "{jobfailed}"
			                                       exit 0
			                                       """)), file=f)
		os.chmod(jobscript, os.stat(jobscript).st_mode | stat.S_IXUSR)
		shell('{self.submitcmd} "{jobscript}"')
		self.startedjobs += 1
		threading.Thread(target=self._wait_for_job, args=(job, callback, error_callback, jobscript, jobfinished, jobfailed)).start()
	
	def _wait_for_job(self, job, callback, error_callback, jobscript, jobfinished, jobfailed):
		while True:
			if os.path.exists(jobfinished):
				#import pdb; pdb.set_trace()
				os.remove(jobfinished)
				os.remove(jobscript)
				self.finish_job(job)
				callback(job)
				return
			if os.path.exists(jobfailed):
				os.remove(jobfailed)
				os.remove(jobscript)
				print_exception(ClusterJobException(job), self.workflow.linemaps)
				error_callback()
				return
			time.sleep(1)
			
	@property
	def tmpdir(self):
		if self._tmpdir is None:		
			while True:
				self._tmpdir = ".snakemake.tmp." + "".join(random.sample(string.ascii_uppercase + string.digits,6))
				if not os.path.exists(self._tmpdir):
					os.mkdir(self._tmpdir)
					break
		return self._tmpdir


def run_wrapper(run, input, output, wildcards, threads, log, linemaps):
	"""
	Wrapper around the run method that handles directory creation and
	output file deletion on error.
	
	Arguments
	run       -- the run method
	input     -- list of input files
	output    -- list of output files
	wildcards -- so far processed wildcards
	threads   -- usable threads
	log       -- path to log file
	"""
	try:
		# execute the actual run method.
		run(input, output, wildcards, threads, log)
		# finish all spawned shells.
		shell.join_all()
	except (Exception, BaseException) as ex:
		# this ensures that exception can be re-raised in the parent thread
		lineno, file = get_exception_origin(ex, linemaps)
		raise RuleException(format_error(ex, lineno, linemaps=linemaps, snakefile=file))