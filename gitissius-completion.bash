#!bash
#
# gitissius-completion
# ===================
#
# Bash completion support for [gitissius](https://github.com/glogiotatidis/gitissius)
#
#
# Installation
# ------------
#
# To achieve gitissius completion nirvana:
#
#   0. Install git-completion.
#
#   1. Install this file. Either:
#
#      a. Place it in a `bash-completion.d` folder:
#
#         * /etc/bash-completion.d
#         * /usr/local/etc/bash-completion.d
#         * ~/bash-completion.d
#
#      b. Copy it somewhere (e.g. ~/.gitissius-completion.bash) and put the following line in your .bashrc:
#
#         source ~/.gitissius-completion.bash
#
#   2. If you are using Git < 1.7.1:
#      Edit git-completion.sh and add the following line to the giant $command case in _git:
#
#      issius) _git_issius ;;
#
#
# The Fine Print
# --------------
#
# Copyright (c) 2012 [DJ van Roermund]()
#
# Distributed under the [MIT License](http://creativecommons.org/licenses/MIT/)

_git_issius () {
   local subcommands="comment myissues show list update pull delete new close push edit"
   local subcommand="$(__git_find_on_cmdline "$subcommands")"
   if [ -z "$subcommand" ]; then
      __gitcomp "$subcommands"
      return
   fi

   case "$subcommand" in
      close|comment|delete|edit)
         case "$cur" in
            -*)
               __gitcomp "--help"
               ;;
            *)
               __gitcomp "$(__gitissius_list_issues)"
               ;;
         esac
         ;;

      show)
         case "$cur" in
            -*)
               __gitcomp "--help --all"
               ;;
            *)
               __gitcomp "$(__gitissius_list_issues)"
               ;;
         esac
         ;;

      list)
         case "$cur" in
            --filter=*)
               cur=${cur:9} # Remove the option, i.e. '--filter=', as bash would otherwise repeat it
               # Not using __gitcomp here, since that adds an unwanted space after the colon
               COMPREPLY=($(compgen -W "assigned_to assigned_to__not assigned_to__exact
                                        assigned_to__startwith created_on created_on__not
                                        created_on__exact created_on__startswith updated_to
                                        updated_to__not updated_to__exact updated_to__startswith
                                        reported_from reported_from__not reported_from__exact
                                        reported_from__startswith status status__not
                                        status__exact status__startswith id id__not id__exact
                                        id__startswith title title__not title__exact
                                        title__startswith type type__not type__exact
                                        type__startswith" -S ":" -- $cur))
               ;;
            --sort=*)
               __gitissius_complete_sort
               ;;
            *)
               __gitcomp "--help --sort= --filter= --all"
               ;;
         esac
         ;;

      myissues)
         case "$cur" in
            --sort=*)
               __gitissius_complete_sort
               ;;
            *)
               __gitcomp "--help --sort= --all"
               ;;
         esac
         ;;

      *)
         __gitcomp "--help"
         ;;
   esac
}

__gitissius_complete_sort () {
   cur=${cur:7} # Remove the option, i.e. '--sort=', as bash would otherwise repeat it
   __gitcomp "assigned_to created_on updated_to reported_from status id title type"
}

__gitissius_list_issues () {
   # Extract valid possibilities by parsing output of `git issius list`
   opts=$(git issius list | head -n -2 | tail -n +3 | awk '{ print $1 }')

   # If are more than one possibilities and no current input, show the complete list of issues
   if [ ${#opts} -gt 5 -a ${#cur} -eq 0 ]; then
      echo 1>&2
      git issius list | head -n -2 1>&2
   fi

   echo $opts
}

# alias __git_find_on_cmdline for backwards compatibility
if [ -z "`type -t __git_find_on_cmdline`" ]; then
   alias __git_find_on_cmdline=__git_find_subcommand
fi
