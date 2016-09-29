Changelog
=========

%%version%% (unreleased)
------------------------

- Reorganized Multiprocessing in integrity_audit. [TheOneHyer]

  integrity_audit now handles all multiprocessing via
  manual daemons. Several bug fixes to ensure
  proper files get analyzed. Standing bug where checksums
  not being written to checksum file.

- Added TODO to integrity_audit. [TheOneHyer]

  Began bug testing integrity_audit. Added TODO to change
  Pool call for analyzing checksums to manual daemons.

- Added ThreadCheck to integrity_audit. [TheOneHyer]

  integrity_audit now implements the old function thread_check
  as the class ThreadCheck. ThreadCheck functions properly.

- ITentatively Finished integrity_audit. [TheOneHyer]

  integrity_audit is complete less testing. Writes checksum files.

- Integrity_audit Verifies File Existence for Checksums. [Alex Hyer]

  Checksum comparision function now ensures that all files
  listed in checksum file exist.

- Added Checksum Comparison to integrity_audit. [TheOneHyer]

  integrity_audit now compares stored checksums to calculated
  ones.

- Added Internal Argument for integrity_audit. [TheOneHyer]

  Added ability to pass algorithm to checksum_analyzer
  function of integrity_audit.

- Added Assertions and Debug to integrity_audit. [TheOneHyer]

  integrity_audit now has many more assertions for file
  and directory existence and permissions with associated
  debug statements.

- Added Warning Messages and TODO to integrity_audit. [TheOneHyer]

  Moved integrity_audit TODO statements to appropriate
  location. Added Warning messages in primary loop of program.

- Added Warning Messages in integrity_audit. [TheOneHyer]

  integrity_audit now catches runtime errors during checksum
  calculations and suppresses them (skips the calculation).
  Error is reported. Also Warns of inaccessible files.

- Added itertools tricks to integrity_audit. [TheOneHyer]

  Python 2.7 does not support sending multiple
  arguments to processes via Pool.map. Added itertools
  trick to permit usage of multiple arguments.

- Added Core Check to integrity_audit. [TheOneHyer]

  integrity_audit now ensures number of threads specified
  by user is valid.

- Added Multiprocessing Pool to integrity_audit. [TheOneHyer]

  integrity_audit now has a processor pool for comparing
  computed file checksums against stored file checksums.

- Updated TODO in integrity_audit. [TheOneHyer]

  Added TODO statement in integrity_audit
  to check number fo cores available.

- Added Log Message to integrity_audit. [TheOneHyer]

  Added numerous log messages to integrity_audit.

- Reorganized Thread-Generation in integrity_audit. [TheOneHyer]

  Conolidated code for thread processing so only one
  function is used.

- Added Logging to integrity_audit. [TheOneHyer]

  integrity_audit now ahs a properly setup logging
  facility for ease of use later.

- Finished Draft of Subprocesses for integrity_audit. [TheOneHyer]

  First draft of function running checksums completed
  for both *nix commands and hashlib.

- Added hashlib to integrity_audit. [TheOneHyer]

  integrity_audit now links to Python
  hashlib functions for itnernal use.

- Added Subprocess Boilerplate to integrity_audit. [TheOneHyer]

  integrity_audity now has some boilerplate code
  for initializing two different daemons based on
  presence/absence of *nix sum command.

- Added Some Framework to integriy_audit. [TheOneHyer]

  Added some multiprocessing boilerplate
  to integrity_audit.

- Added integrity_audit and updated utils.json. [TheOneHyer]

  Utils.json is a more modern version from a
  pervious server and added integrity_audit startup.

- Added Ability to get File Structure Info. [TheOneHyer]

  Added Classes and main function loop to obtain
  info on directory structure.

- Added integrity_audit.py and ChangeLog.rst. [TheOneHyer]

  Added ChangeLog.rst for use by gitchangelog
  and added metadata for integrity_audit.py

- Remove utils.txt. [Christopher Thornton]

- Rename utils.txt to utils.json. [Christopher Thornton]

- Add argument -d to list of arguments to parse. [Christopher Thornton]

- Added additional error catching at most major steps. [Christopher
  Thornton]

- Change subcommand display to show. [Christopher Thornton]

- Fixed utils.py append mode. [Alex Hyer]

- Added autocomplete to prgram editing. [Alex Hyer]

- Added ability to specify multiple categories in utils.py. [Alex Hyer]

- Added autocomplete feature to utils.py. [Alex Hyer]

- Added category viewing options to utils.py. [Alex Hyer]

- Fixed bug with previous version in utils.py. [Alex Hyer]

- Added categories to utils.py and added manually curated list for
  editing items under relevant_values. [Alex Hyer]

- Remove deletion of backup when rsync fails. [Christopher Thornton]

- Add snapshot creation. [Christopher Thornton]

- Cleanup output. [Christopher Thornton]

- Merge branch 'master' of
  ssh://winogradsky.biology.utah.edu:53211/srv/repos/system.
  [Christopher Thornton]

- Modify how utils accepts multiple arguments. [Christopher Thornton]

- Correct location for config file. [Christopher Thornton]

- Return correct thing from match_test. [Christopher Thornton]

- Fix punctuation error. [Christopher Thornton]

- Fix spelling error in match_test. [Christopher Thornton]

- Modify how utils checks for existing programs in the database.
  [Christopher Thornton]

- Remove dependency on snapshots and add additional error checking.
  [Christopher Thornton]

- Make log file optional. [Christopher Thornton]

- Merge branch 'master' of /./srv/repos/system. [Alex Hyer]

- Add functions to check success/failure. [Christopher Thornton]

- Update utils.txt. [Christopher Thornton]

- Heavily Modified integrity_check.py. [Alex Hyer]

  The core functionality of integrity_check.py remains unchanged.
  integrity_check.py now parallelizes checking the core function
  of computing and checking checksums. Additoinally, the program
  now outputs to a user-defined log file instead of syslog.
  integrity_check.py command line now requries three arguments:

  integrity_check.py directory_to_analyze log_file core_number

  If core_number is unspecified, it defaults to one.

- Add class to default to usage message. [Christopher Thornton]

- Change path to text file. [Christopher Thornton]

- Finish edit subcommand. [Christopher Thornton]

- Subcommands for different desired action. [Christopher Thornton]

- Ignore case when searching for specific programs. [Christopher
  Thornton]

- Fixed plurality inconsistencies in usage message. [Christopher
  Thornton]

- Fix to comply with standard conventions and add support for multiple
  program input. [Christopher Thornton]

- Add script to display list of bioinformatics programs to users on the
  server. [Christopher Thornton]

- Merge branch 'master' of /srv/repos/system. [root]

- Finish backup script. [Christopher Thornton]

- Add additional logging. [root]

- Fix obtaining files from data path. [Christopher Thornton]

- Initial commit. [Christopher Thornton]


