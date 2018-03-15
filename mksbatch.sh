#!/usr/bin/env bash

show_help() {
cat << EOF
Usage: ${0##*/} [-h] [-e] sbatch_file
SBatch Script Generator

positional arguments:
  sbatch_file     name of sbatch file to create

optional arguments:
  -h              display this help message and exit
  -e              text editor to edit sbatch_file with [default: vim]
  -s              set a new default editor
EOF
}

set_editor(){
echo ${SET} > ${HOME}/.new_sbatch
}

# parse command line arguments
OPTIND=1;
EDITOR="/usr/bin/nano"
if [ -f ${HOME}/.mksbatch ]; then
    EDITOR=$(cat ${HOME}/.new_sbatch)
fi
if [[ $# -eq 0 ]] ; then
    show_help;
    exit 0;
fi
while getopts "h:?:e:s:" opt; do
    case "$opt" in
        h)
            show_help;
            exit 0
            ;;
        e)  EDITOR=$(whereis -b ${OPTARG} | cut -f 2 -d ' ')
            ;;
        s)  SET=$(whereis -b ${OPTARG} | cut -f 2 -d ' ');
            set_editor;
            exit 0
            ;;
        ?)
            show_help;
            exit 0
            ;;
    esac
done
sbatch_file="${@:$OPTIND:1}";

cat << EOF > ${sbatch_file}
#!/usr/bin/env bash

#SBATCH --partition batch  # Partition to use for job
#SBATCH --output job.out # Captures STDOUT
#SBATCH --error job.err  # Captures STDERR
#SBATCH --nodes 1  # Number of nodes this job can use
#SBATCH --ntasks 1  # Number of tasks this job will spawn simultaneously
#SBATCH --cpus-per-task 1  # Number of CPUs each task needs
#SBATCH --mem-per-cpu 2G  # Amount of memory each CPU will require
#SBATCH --time 3-0  # Approx. number of days this job will take to complete

# Notes:
# Total CPUs = ntasks X cpus-per-task
# Total memory = ntasks X cpus-per-task X mem-per-cpu
# --nodes should never be greater than --ntasks
# You should absolutely edit --output and --error


EOF

${EDITOR} ${sbatch_file}