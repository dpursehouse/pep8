#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tempfile
import unittest

from processes import run_cmd
from processes import ChildExecutionError
from processes import ChildRuntimeError
from processes import ChildSignalledError
from processes import ChildStartupError


SCRIPT_SUCCESS = '''#!/bin/sh
echo "output"
exit 0
'''

SCRIPT_FAIL_RUNTIME_ERROR = '''#!/bin/sh
echo "output"
echo "runtime error" >&2
exit 1
'''

SCRIPT_FAIL_SIGNALLED = '''#!/bin/sh
echo "output"
echo "signalled" >&2
MYPID=`cut -d ' ' -f 4 /proc/self/stat`
kill -s KILL $MYPID
'''


class TestRunCmd(unittest.TestCase):
    """Test that the run_cmd method behaves correctly.
    """

    def _run_shell_script(self, script):
        ''' Create a temporary file, write the contents of `script` to it,
        and then execute it using the run_cmd method.
        Return the results of run_cmd.
        Raise some form of ChildExecutionError if an error occurs.
        '''
        script_file = tempfile.NamedTemporaryFile('wt')
        script_file.write(script)
        script_file.flush()
        return run_cmd(['sh', script_file.name])

    def test_success(self):
        ''' Test that the run_cmd method behaves correctly when
        the executed command is successful.
        '''
        ret, out, err = self._run_shell_script(SCRIPT_SUCCESS)
        self.assertEquals(ret, 0)
        self.assertEquals(out.strip(), "output")
        self.assertEquals(err, "")

    def test_fail_runtime_error(self):
        ''' Test that the run_cmd method behaves correctly when
        the executed command exits with a runtime error, i.e. non-zero
        exit status.
        '''
        try:
            ret, out, err = self._run_shell_script(SCRIPT_FAIL_RUNTIME_ERROR)
        except ChildRuntimeError, e:
            ret = e.result[0]
            out = e.result[1].strip()
            err = e.result[2].strip()
            self.assertEquals(ret, 1)
            self.assertEquals(out, "output")
            self.assertEquals(err, "runtime error")
            return
        except:
            pass

        # If we reach this point, it means the expected exception was not
        # raised, and thus the test has failed.
        self.fail("Exception ChildRuntimeError was not raised")

    def test_fail_signalled(self):
        ''' Test that the run_cmd method behaves correctly when
        the executed command dies of a signal.
        '''
        try:
            ret, out, err = self._run_shell_script(SCRIPT_FAIL_SIGNALLED)
        except ChildSignalledError, e:
            ret = e.result[0]
            out = e.result[1].strip()
            err = e.result[2].strip()
            self.assertEquals(ret, -9)
            self.assertEquals(out, "output")
            self.assertEquals(err, "signalled")
            return
        self.fail("Exception ChildSignalledError was not raised")

    def test_fail_non_existent_executable(self):
        ''' Test that the run_cmd method behaves correctly when
        the specified executable does not exist.
        '''
        try:
            ret, out, err = run_cmd(['i_do_not_exist.sh'])
        except ChildStartupError:
            return
        except:
            pass

        self.fail("Exception ChildStartupError was not raised")

if __name__ == '__main__':
    unittest.main()
