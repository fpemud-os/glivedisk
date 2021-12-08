#!/usr/bin/env python3

# glivedisk - gentoo live disk building
#
# Copyright (c) 2020-2021 Fpemud <fpemud@sina.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


__package__ = 'glivedisk'

__version__ = '0.0.1'

__author__ = 'Fpemud <fpemud@sina.com>'


from ._seed import verify_seed_stage_dir
from ._seed import CloudGentooStage3

from ._workdir import WorkDir
from ._workdir import WorkDirChrooter

from ._ubuilder import UserSpaceBuilder
from ._ubuilder import UserSpaceBuildProgress

from ._kbuilder import Genkernel
from ._kbuilder import GenkernelProgress

from ._exporter import get_exporter
from ._exporter import Exporter

from ._errors import SettingsError
from ._errors import SeedStageError
from ._errors import WorkDirVerifyError
