import sys
import time
import cmd2 as cli
from cmd2 import style, ansi

class prompt(cli.Cmd):
    def __init__(self, config, commands, clilogger):
        super().__init__(persistent_history_file=config.HISTORY, persistent_history_length=config.HISTORY_LEN)
        self.config = config
        self.commands = commands
        self.clilogger = clilogger
        self.hidden_commands.append('py')
        self.hidden_commands.append('edit')
        self.prompt = style('NHC> ', fg='blue', bold=True)
        self.intro = style('Welcome! Type ? to list commands', fg='blue', bg='white', bold=True)
        self.locals_in_py = True
        self.default_category = 'cmd2 Built-in Commands'

    def precmd(self, line):
        self.clilogger.set_cmd_from_mqtt(False)
        return line

    def postcmd(self, stop: bool, line: str) -> bool:
        # give some time, otherwise logger prints between response
        time.sleep(self.config.RESPONSE_RETRY)
        # make sure prompt is visible after every command
        self.clilogger.cli_neutral("")
        return stop

    @cli.with_argument_list
    @cli.with_category("NHC")
    def do_devices(self, args):
        self.commands.do_devices(args)
 
    def help_devices(self):
        self.commands.help_devices()

    @cli.with_argument_list
    @cli.with_category("NHC")
    def do_light(self, args):
        self.commands.do_light(args)
 
    def help_light(self):
        self.commands.help_light()

    @cli.with_argument_list
    @cli.with_category("NHC")
    def do_dimmer(self, args):
        self.commands.do_dimmer(args)
 
    def help_dimmer(self):
        self.commands.help_dimmer()
