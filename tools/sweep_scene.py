#!/usr/bin/env python3

import sys
import os
import argparse
import json
import subprocess
import tempfile
import statistics

def compute_stddev(values):
    stdev = 0.0 if len(values) <= 1 else statistics.stdev(values)
    avg = statistics.mean(values)
    return avg, stdev

def run_test(sweep, config, iterations, stat_file, adb):
    config_results = []
    for _ in range(iterations):
        print('Running scene with config:', config)
        subprocess.check_call(sweep)
        print('Ran scene ...')

        if adb:
            subprocess.check_call(['adb', 'pull', '/data/local/tmp/granite/stat.json', stat_file])

        with open(stat_file, 'r') as f:
            json_data = f.read()
            parsed = json.loads(json_data)
            config_results.append(parsed['averageFrameTimeUs'])

    avg, stddev = compute_stddev(config_results)
    return avg, stddev

def main():
    parser = argparse.ArgumentParser(description = 'Script for running automated performance tests.')
    parser.add_argument('--scene',
                        help = 'The glTF/glB scene to test')
    parser.add_argument('--android-viewer-binary',
                        help = 'Path to android binary')
    parser.add_argument('--texcomp',
                        help = 'Which texture compression to use for LDR textures',
                        type = str)
    parser.add_argument('--optimized-scene',
                        help = 'Path where a processed scene is placed.',
                        type = str)
    parser.add_argument('--environment-texcomp',
                        help = 'Which texture compression to use for environments',
                        type = str)
    parser.add_argument('--environment-cube',
                        help = 'Cubemap texture',
                        type = str)
    parser.add_argument('--environment-reflection',
                        help = 'Reflection texture',
                        type = str)
    parser.add_argument('--environment-irradiance',
                        help = 'Irradiance texture',
                        type = str)
    parser.add_argument('--extra-lights',
                        help = 'Extra lights',
                        type = str)
    parser.add_argument('--extra-cameras',
                        help = 'Extra cameras',
                        type = str)
    parser.add_argument('--configs',
                        help = 'Which config files to sweep through',
                        type = str,
                        nargs = '+')
    parser.add_argument('--builtin',
                        help = 'Where to find the builtin assets/shaders',
                        type = str)
    parser.add_argument('--gen-configs',
                        help = 'Automatically generate configs to sweep through',
                        action = 'store_true')
    parser.add_argument('--width',
                        help = 'Resolution X',
                        type = int)
    parser.add_argument('--height',
                        help = 'Resolution Y',
                        type = int)
    parser.add_argument('--frames',
                        help = 'Number of frames',
                        type = int)
    parser.add_argument('--iterations',
                        help = 'Number of iterations',
                        type = int)


    args = parser.parse_args()

    if args.optimized_scene:
        scene_build = ['./tools/gltf-repacker']
        scene_build.append(args.scene)

        scene_build.append('--output')
        scene_build.append(args.optimized_scene)

        if args.texcomp:
            scene_build.append('--texcomp')
            scene_build.append(args.texcomp)

        if args.environment_texcomp:
            scene_build.append('--environment-texcomp')
            scene_build.append(args.environment_texcomp)
        if args.environment_cube:
            scene_build.append('--environment-cube')
            scene_build.append(args.environment_cube)
        if args.environment_reflection:
            scene_build.append('--environment-reflection')
            scene_build.append(args.environment_reflection)
        if args.environment_irradiance:
            scene_build.append('--environment-irradiance')
            scene_build.append(args.environment_irradiance)

        if args.extra_lights:
            scene_build.append('--extra-lights')
            scene_build.append(args.extra_lights)
        if args.extra_cameras:
            scene_build.append('--extra-cameras')
            scene_build.append(args.extra_cameras)

        print('Building scene with arguments', scene_build)
        subprocess.check_call(scene_build)
        print('Built scene ...')

        sweep_path = args.optimized_scene
    else:
        sweep_path = args.scene

    if args.android_viewer_binary:
        print('Setting up directories ...')
        subprocess.check_call(['adb', 'shell', 'mkdir', '-p', '/data/local/tmp/granite'])
        subprocess.check_call(['adb', 'shell', 'mkdir', '-p', '/data/local/tmp/granite/cache'])
        subprocess.check_call(['adb', 'shell', 'mkdir', '-p', '/data/local/tmp/granite/assets'])
        print('Pushing granite binary ...')
        subprocess.check_call(['adb', 'push', args.android_viewer_binary, '/data/local/tmp/granite/gltf-viewer-headless'])
        subprocess.check_call(['adb', 'shell', 'chmod', '+x', '/data/local/tmp/granite/gltf-viewer-headless'])

        print('Pushing test scene ...')
        subprocess.check_call(['adb', 'push', sweep_path, '/data/local/tmp/granite/scene.glb'])
        print('Pushing builtin assets ...')
        subprocess.check_call(['adb', 'push', args.builtin, '/data/local/tmp/granite/'])

        asset_dir = os.path.dirname(sweep_path)
        for dir, subdir, file_list in os.walk(asset_dir):
            for f in file_list:
                if os.path.splitext(f)[1] == '.ktx':
                    print('Pushing texture: ', os.path.join(dir, f), 'to', os.path.basename(f))
                    subprocess.check_call(['adb', 'push', os.path.join(dir, f), '/data/local/tmp/granite/' + os.path.basename(f)])

    f, stat_file = tempfile.mkstemp()
    f_c, config_file = tempfile.mkstemp()
    os.close(f)
    os.close(f_c)

    if (not args.width) or (not args.height) or (not args.frames):
        sys.stderr.write('Need width, height and frames.\n')
        sys.exit(1)

    if args.android_viewer_binary:
        base_sweep = ['adb', 'shell', '/data/local/tmp/granite/gltf-viewer-headless', '--frames', str(args.frames),
                      '--width', str(args.width),
                      '--height', str(args.height), '/data/local/tmp/granite/scene.glb',
                      '--stat', '/data/local/tmp/granite/stat.json',
                      '--fs-builtin /data/local/tmp/granite/assets',
                      '--fs-assets /data/local/tmp/granite/assets',
                      '--fs-cache /data/local/tmp/granite/cache']
    else:
        base_sweep = ['./viewer/gltf-viewer-headless', '--frames', str(args.frames),
                      '--width', str(args.width),
                      '--height', str(args.height), sweep_path,
                      '--stat', stat_file]

    results = []
    iterations = args.iterations if args.iterations else 1

    if args.configs:
        for config in args.configs:
            if args.android_viewer_binary:
                sweep = base_sweep + ['--config', '/data/local/tmp/granite/config.json']
                subprocess.check_call(['adb', 'push', config, '/data/local/tmp/granite/config.json'])
            else:
                sweep = base_sweep + ['--config', config]
            avg, stddev = run_test(sweep, config, iterations, stat_file, args.android_viewer_binary != None)
            results.append((config, avg, stddev))
    elif args.gen_configs:
        for renderer in ['forward', 'deferred']:
            for msaa in [1, 4]:
                for prepass in [False, True]:
                    if msaa != 1 and renderer == 'deferred':
                        continue
                    if prepass and renderer == 'deferred':
                        continue
                    for clustered in [False, True]:
                        for hdr_bloom in [False, True]:
                            for shadows in [False, True]:
                                for pos_shadows in [False, True]:
                                    c = {}
                                    c['renderer'] = renderer
                                    c['hdrBloom'] = hdr_bloom
                                    c['msaa'] = msaa
                                    c['clusteredLights'] = clustered
                                    c['directionalLightShadows'] = shadows
                                    c['forwardDepthPrepass'] = prepass
                                    c['clusteredLightsShadows'] = pos_shadows
                                    with open(config_file, 'w') as f:
                                        json.dump(c, f)

                                    if args.android_viewer_binary:
                                        sweep = base_sweep + ['--config', '/data/local/tmp/granite/config.json']
                                        subprocess.check_call(['adb', 'push', config_file, '/data/local/tmp/granite/config.json'])
                                    else:
                                        sweep = base_sweep + ['--config', config_file]

                                    avg, stddev = run_test(sweep, config_file, iterations, stat_file, args.android_viewer_binary != None)

                                    config_name = {}
                                    config_name['renderer'] = renderer
                                    config_name['msaa'] = msaa
                                    config_name['prepass'] = prepass
                                    config_name['clustered'] = clustered
                                    config_name['hdr_bloom'] = hdr_bloom
                                    config_name['shadows'] = shadows
                                    config_name['pos_shadows'] = pos_shadows
                                    results.append((config_name, avg, stddev))

    for res in results:
        print(res)
    os.remove(stat_file)
    os.remove(config_file)

if __name__ == '__main__':
    main()
