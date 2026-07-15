# load_adapters.py
#
# Phase 4: Adapter deployments.
#
# This phase is deliberately limited compared to Phases 1–3 because the key
# per-connection-instance config (FTP hosts, credentials, JNDI names like
# eis/Ftp/EO_FtpAdapter) lives inside the deployment plan files, not in the
# domain config MBean tree.  The extract captures planPath and sourcePath,
# and — when connectionInstances is populated — the JNDI names of each
# instance.  What it cannot capture is the content of those connection
# instances (host, port, username, password).
#
# What this phase does:
#   - Reports which adapter deployments were exported
#   - If sourcePath and planPath are present and accessible on the target,
#     uses the WLST deploy() command to redeploy the adapter with its plan
#   - Warns clearly for any adapters where the plan content is missing
#
# What you will need to do manually (or extend this script to handle):
#   - Supply connection-instance credentials that were not in the extract
#   - Re-map file paths (sourcePath, planPath) if the domain home differs
#   - Re-enter any passwords inside plan files
#
# Path remapping: add adapter.sourcepath.<AdapterName> and
# adapter.planpath.<AdapterName> to the properties file to override the
# extracted paths for a target environment.
#
# WLST globals used directly — must run inside WLST.

import sys
import os
from load_serialize import get, get_str, get_list


def _is_dry_run(env):
    return get(env, 'dry_run', False)


def _map_target(name, env):
    target_map = get(env, 'targets', {})
    return str(target_map.get(str(name), str(name)))


def _resolve_path(key, extracted_path, env):
    # Allow the properties file to override a path for this environment.
    overrides = get(env, 'adapter_paths', {})
    override = overrides.get(key)
    if override:
        return str(override)
    return extracted_path


def load_adapters(data, env):
    print ''
    print '=== Phase 4: Adapter deployments ==='
    print ''
    print 'NOTE: adapter connection-instance content (host, port, credentials)'
    print '      is NOT available from the domain config MBean tree and was not'
    print '      captured by the extract.  Review warnings below.'
    print ''

    adapters = get_list(data, 'adapterDeployments')
    if not adapters:
        print 'No user adapter deployments in extract.'
        return

    for adapter in adapters:
        name = get_str(adapter, 'name')
        if not name:
            continue

        source_path = _resolve_path('sourcepath.' + name,
                                    get_str(adapter, 'sourcePath'), env)
        plan_path = _resolve_path('planpath.' + name,
                                  get_str(adapter, 'planPath'), env)
        raw_targets = get_list(adapter, 'targets')
        instances = get_list(adapter, 'connectionInstances')

        print '  Adapter: ' + name
        print '    sourcePath: ' + (source_path or '(none)')
        print '    planPath:   ' + (plan_path or '(none)')

        if instances:
            print '    connectionInstances: ' + ', '.join(instances)
        else:
            print '    connectionInstances: NOT CAPTURED — supply manually'

        if not source_path:
            print '    WARNING: no sourcePath — cannot deploy without it'
            continue

        if not os.path.exists(source_path):
            print '    WARNING: sourcePath not accessible on this host: ' + source_path
            print '             Set adapter.sourcepath.' + name + ' in properties to override'
            continue

        if plan_path and not os.path.exists(plan_path):
            print '    WARNING: planPath not accessible on this host: ' + plan_path
            print '             Set adapter.planpath.' + name + ' in properties to override'
            plan_path = None

        if _is_dry_run(env):
            print '    [dry-run] Would deploy: ' + name
            continue

        # Build the targets string for deploy().
        mapped_targets = [_map_target(t, env) for t in raw_targets]
        targets_str = ','.join(mapped_targets) if mapped_targets else None

        print '    Deploying: ' + name
        try:
            if plan_path:
                deploy(name, source_path,
                       targets=targets_str,
                       planPath=plan_path,
                       stageMode='nostage',
                       block='true')
            else:
                deploy(name, source_path,
                       targets=targets_str,
                       stageMode='nostage',
                       block='true')
            print '    Deployed OK: ' + name
        except Exception:
            print '    ERROR deploying ' + name + ': ' + str(sys.exc_info()[1])
            print '    (continuing with remaining adapters)'
