Changelog
=========

%%version%% (unreleased)
------------------------

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


