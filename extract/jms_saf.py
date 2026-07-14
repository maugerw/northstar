# jms_saf.py
#
# WLST-dependent extraction of SAF agents and SAF imported destinations
# (plus their remote contexts).
#
# The live configuration MBean (cmo) is passed in as an argument rather than
# relied on as a WLST global.

from jms_filters import get_targets, is_system_saf
from jms_serialize import to_long, to_boolean, safe, _name_of


def extract_saf_agents(cmo, extract_data, system_data):
    print 'Extracting SAF Agents...'

    safAgents = cmo.getSAFAgents()

    for saf in safAgents:
        saf_dict = {}
        saf_name = str(saf.getName())
        saf_dict["name"] = saf_name
        saf_dict["targets"] = get_targets(saf)

        saf_dict["store"] = safe(saf, 'getStore', _name_of)

        # --- Additional SAF fields ---
        saf_dict["serviceType"] = safe(saf, 'getServiceType')
        saf_dict["retryDelayBase"] = safe(saf, 'getDefaultRetryDelayBase', to_long)
        saf_dict["retryDelayMaximum"] = safe(saf, 'getDefaultRetryDelayMaximum', to_long)
        saf_dict["retryDelayMultiplier"] = safe(saf, 'getDefaultRetryDelayMultiplier', to_long)
        saf_dict["timeToLive"] = safe(saf, 'getDefaultTimeToLive', to_long)
        saf_dict["loggingEnabled"] = safe(saf, 'isLoggingEnabled', to_boolean)
        saf_dict["windowSize"] = safe(saf, 'getWindowSize', to_long)
        saf_dict["acknowledgeInterval"] = safe(saf, 'getAcknowledgeInterval', to_long)

        if is_system_saf(saf_name):
            system_data["systemSafAgents"].append(saf_dict)
        else:
            extract_data["safAgents"].append(saf_dict)


def extract_saf_imported_destinations(cmo, extract_data, system_data):
    print 'Extracting SAF Imported Destinations...'

    try:
        imported_dests = cmo.getSAFImportedDestinations()

        for dest in imported_dests:
            # Compute the name once and reuse it for the dict and the
            # user/system classification (instead of calling getName() twice).
            dest_name = str(dest.getName())
            dest_dict = {}
            dest_dict["name"] = dest_name
            dest_dict["targets"] = get_targets(dest)

            dest_dict["remoteJNDIName"] = safe(dest, 'getRemoteJNDIName')
            dest_dict["localJNDIName"] = safe(dest, 'getLocalJNDIName')
            dest_dict["remoteContext"] = safe(dest, 'getSAFRemoteContext', _name_of)
            dest_dict["qos"] = safe(dest, 'getQualityOfService')
            dest_dict["timeToLive"] = safe(dest, 'getTimeToLiveDefault', to_long)
            dest_dict["loggingEnabled"] = safe(dest, 'isLoggingEnabled', to_boolean)

            dest_is_system = is_system_saf(dest_name)
            if dest_is_system:
                system_data["systemSafImportedDestinations"].append(dest_dict)
            else:
                extract_data["safImportedDestinations"].append(dest_dict)

            rc_dict = None
            try:
                rc = dest.getSAFRemoteContext()
                if rc:
                    rc_dict = {}
                    rc_dict["name"] = str(rc.getName())
                    rc_dict["providerURL"] = safe(rc, 'getProviderURL')
                    rc_dict["initialContextFactory"] = safe(rc, 'getInitialContextFactory')
                    rc_dict["connectionURL"] = safe(rc, 'getConnectionURL')

                if rc_dict:
                    if dest_is_system:
                        system_data["safRemoteContexts"][rc_dict["name"]] = rc_dict
                    else:
                        extract_data["safRemoteContexts"][rc_dict["name"]] = rc_dict
            except Exception:
                pass
    except Exception:
        pass
