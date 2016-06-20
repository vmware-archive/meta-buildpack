#!/usr/bin/env python

# tile-generator
#
# Copyright (c) 2015-Present Pivotal Software, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import json
import hashlib
import subprocess

""" detect """

def detect(build_dir):
	buildpack = detect_buildpack(build_dir).rstrip('\n')
	decorators = detect_decorators(build_dir)
	if len(decorators) == 0:
		info = '(no decorators apply)'
	elif len(decorators) < 2:
		info = '(with decorator ' + decorators[0] + ')'
	else:
		info = '(with decorators ' + ', '.join(decorators) + ')'
		if len(info) > 128:
			info = '(with decorators)'
	if (len(buildpack) + len(info)) >= 255:
		buildpack = buildpack[:251 - len(info)] + '...'
	print buildpack, info

def detect_buildpack(build_dir):
	for bp in buildpacks():
		try:
			buildpack_dir = getarg('buildpacksDir')
			bin_detect = os.path.join(buildpack_dir, bp, "bin", "detect")
			buildpack = subprocess.check_output( [ bin_detect, build_dir ] )
			print >> sys.stderr, "[meta-buildpack] Selected buildpack", buildpack
			save_state('buildpack_name', buildpack)
			save_state('buildpack_path', bp)
			return buildpack
		except OSError: # Buildpack is mal-formed
			print >> sys.stderr, "[meta-buildpack]", bin_detect, "not found"
			pass
		except subprocess.CalledProcessError as error:
			pass
	print >> sys.stderr, "[meta-buildpack] No other buildpack selected"
	sys.exit(1)

def detect_decorators(build_dir):
	decorators = []
	for bp in buildpacks():
		try:
			buildpack_dir = getarg('buildpacksDir')
			bin_decorate = os.path.join(buildpack_dir, bp, "bin", "decorate")
			decorator = subprocess.check_output( [ bin_decorate, build_dir ] )
			print >> sys.stderr, "[meta-buildpack] Selected decorator", decorator
			decorators.append({
				'decorator_name': decorator.rstrip('\n'),
				'decorator_path': bp
			})
		except OSError: # Buildpack is not a decorator
			pass
		except subprocess.CalledProcessError as error:
			pass
	save_state('decorators', decorators)
	return [ d.get('decorator_name') for d in decorators ]

""" compile """

def compile(build_dir, cache_dir, env_dir):
	buildpack_name = get_state('buildpack_name')
	buildpack_path = get_state('buildpack_path')
	compile_buildpack(buildpack_name, buildpack_path, build_dir, cache_dir, env_dir)
	decorators = get_state('decorators')
	for decorator in decorators:
		decorator_name = decorator['decorator_name']
		decorator_path = decorator['decorator_path']
		compile_buildpack(decorator_name, decorator_path, build_dir, cache_dir, env_dir)

def compile_buildpack(name, path, build_dir, cache_dir, env_dir):
	print >> sys.stderr, "[meta-buildpack] Compiling with", name
	try:
		buildpack_dir = getarg('buildpacksDir')
		bin_compile = os.path.join(buildpack_dir, path, "bin", "compile")
		subprocess.check_call( [ bin_compile, build_dir, cache_dir, env_dir ] )
	except OSError: # Buildpack is mal-formed
		print >> sys.stderr, "[meta-buildpack]", bin_compile, "not found"
		sys.exit(2)
	except subprocess.CalledProcessError as error:
		print >> sys.stderr, "[meta-buildpack] Passing on exit code ", error.returncode
		sys.exit(error.returncode)

""" release """

def release(build_dir):
	buildpack_name = get_state('buildpack_name')
	buildpack_path = get_state('buildpack_path')
	try:
		buildpack_dir  = getarg('buildpacksDir')
		bin_release = os.path.join(buildpack_dir, buildpack_path, "bin", "release")
		subprocess.check_call( [ bin_release, build_dir ] )
	except OSError: # Buildpack is mal-formed
		print >> sys.stderr, "[meta-buildpack]", bin_release, "not found"
		sys.exit(2)
	except subprocess.CalledProcessError as error:
		print >> sys.stderr, "[meta-buildpack] Passing on exit code ", error.returncode
		sys.exit(error.returncode)

""" common helpers """

args = None

def getarg(arg):
	global args
	if args is None:
		args = {}
		argv = os.getenv('BUILD_CMD').split()
		if argv is None or len(argv) < 1 or not argv[0].endswith('/builder'):
			print >> sys.stderr, "Environment variable BUILD_CMD is expected to be set to the builder command line"
			print >> sys.stderr, "Found BUILD_CMD: ", os.getenv('BUILD_CMD')
			sys.exit(2)
		for argi in argv[1:]:
			if not argi.startswith('-'):
				print >> sys.stderr, "All builder arguments are expected to start with a dash (-)"
				print >> sys.stderr, "Found", argi
				sys.exit(2)
			parts = argi.lstrip('-').split('=', 1)
			if len(parts) != 2:
				print >> sys.stderr, "All builder arguments are expected to be of the form -key=value"
				print >> sys.stderr, "Found", argi
				sys.exit(2)
			key = parts[0]
			value = parts[1]
			args[key] = value
	value = args.get(arg)
	if value is None:
		print >> sys.stderr, "BUILD_CMD is missing argument", '-' + arg
		sys.exit(2)
	return value

buildpack_paths = None

def buildpacks():
	global buildpack_paths
	if buildpack_paths is None:
		buildpack_self = os.path.abspath(__file__)
		buildpack_order = getarg('buildpackOrder').split(',')
		buildpack_paths = [ buildpack_path(bp) for bp in buildpack_order ]
		buildpack_paths = [ bp for bp in buildpack_paths if bp not in buildpack_self ]
	return buildpack_paths

def buildpack_path(buildpack):
	m = hashlib.md5()
	m.update(buildpack)
	return m.hexdigest()

saved_state = None

def load_state():
	global saved_state
	if saved_state is None:
		try:
			with open('.meta-buildpack.state', 'rb') as state_file:
				saved_state = json.load(state_file)
		except:
			saved_state = {}

def save_state(key, value):
	global saved_state
	load_state()
	saved_state[key] = value
	with open('.meta-buildpack.state', 'wb') as state_file:
		json.dump(saved_state, state_file)

def get_state(key):
	global saved_state
	load_state()
	value = saved_state.get(key, None)
	if value is None:
		print >> sys.stderr, "Saved state is missing value for", key
	return value
