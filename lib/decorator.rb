require "yaml"
require "json"
require "fileutils"

$LOAD_PATH.unshift '/var/vcap/packages/dea_next/buildpacks/lib'

require "buildpack"

def detect(build_dir)
	exit 1 if is_compiling?
	$stdout.puts "decorator-buildpack"
	exit 0
end

def compile(build_dir, cache_dir, env_dir)
	begin
		set_compiling
		buildpacks = Buildpacks::Buildpack.from_file(config_file)
		detected_buildpack = buildpacks.build_pack
		detected_buildpack.compile
		buildpacks.save_buildpack_info
	rescue Buildpacks::NoAppDetectedError
		exit 1
	rescue => e
		$stderr.puts "#{e}"
		exit 1
	ensure
		clear_compiling
	end
end

def release(build_dir)
	start_command = staging_info["start_command"]
	release_info = {
		"default_process_types" => { "web" => start_command }
	}
	release_info
end

private

def config_file
	pattern = "/var/vcap/data/dea_next/staging/*/plugin_config"
	Dir[pattern].each { |config| return config }
	$stderr.puts "Decorator-buildpack could not find config file"
	$stderr.puts "No decorators will be run"
	exit 1
end

def staging_info_file
	"/tmp/staged/staging_info.yml"
end

def compiling_flag
	@application_version ||= begin
		vcap_application = JSON.parse(ENV["VCAP_APPLICATION"])
		application_version = vcap_application["application_version"]
	end
	"/tmp/decorator-" + @application_version + "-compiling"
end

def is_compiling?
	File.exists?(compiling_flag)
end

def set_compiling
	File.open(compiling_flag, "w") {}
end

def clear_compiling
	File.delete(compiling_flag)
end

def staging_info
	@staging_info ||= File.open(staging_info_file, 'rb') do |f|
		YAML.load(f)
	end
end
