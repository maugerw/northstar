# jms_serialize.py
#
# Pure (WLST-independent) serialization helpers.
# These functions have no dependency on the live WLST interpreter (cmo,
# connect(), domainConfig()), so they can be imported and unit-tested in
# plain CPython/Jython 2.

def safe(obj, accessor, conv=None):
    # Call a WLST accessor and normalise the result, swallowing the
    # version-specific attribute errors that are common under WLST (different
    # WLS versions expose slightly different getters). Returns None when the
    # accessor is missing / raises or yields None; otherwise the converted
    # value (conv applied) or its string form. This collapses the pervasive
    #   try:
    #       v = obj.getX()
    #       if v is not None: field = conv(v)
    #   except:
    #       pass
    # idiom into a single call, e.g. safe(q, 'getRedeliveryDelay', to_long).
    #
    # IMPORTANT: the accessor is passed as a *method name string* (not as a
    # bound method like obj.getX) so that the attribute lookup itself happens
    # INSIDE the guarded block. Passing obj.getX would resolve the attribute at
    # the call site and raise AttributeError before safe() ever runs, on WLST
    # versions / mbean types that do not expose that getter.
    try:
        fn = getattr(obj, accessor, None)
    except Exception:
        return None
    if fn is None:
        return None
    try:
        value = fn()
    except Exception:
        return None
    if value is None:
        return None
    if conv is not None:
        return conv(value)
    return str(value)


def _name_of(obj):
    # Conversion helper for accessors that return an mbean whose getName() is
    # the value of interest (e.g. getErrorDestination, getStore).
    return str(obj.getName())


def to_long(value):
    # Convert a numeric WLST value to a Python integer for the JSON output.
    # Returns None only when the value itself is None (so a real 0 is kept).
    if value is None:
        return None
    try:
        return long(value)
    except Exception:
        try:
            return int(value)
        except Exception:
            return str(value)

def to_boolean(value):
    # Convert a WLST boolean to a real Python bool for JSON output.
    #
    # WLST/Jython represents booleans inconsistently: a Java Boolean stringifies
    # to 'true'/'false', but a Java primitive boolean surfaces under Jython 2.2
    # (which has no real bool type) as the int 1/0, stringifying to '1'/'0'.
    # The original check (str(value).lower() == 'true') therefore reported EVERY
    # genuinely-true primitive boolean as False (e.g. isDefaultTargetingEnabled
    # returns 1, '1' != 'true'). Accept all common truthy representations.
    if value is None:
        return None
    try:
        s = str(value).strip().lower()
    except Exception:
        return None
    return s in ('true', '1', 'yes', 'on', 't', 'y')

def _is_dict(obj):
    # type()-based check so we never pass a possibly-non-class object to
    # isinstance() (older Jython/WLST interpreters raise "isinstance() arg 2
    # must be a class, type, or tuple ..." for builtins like bool).
    try:
        return isinstance(obj, dict)
    except Exception:
        return hasattr(obj, 'keys') and hasattr(obj, '__getitem__')


def _is_list(obj):
    try:
        return isinstance(obj, (list, tuple))
    except Exception:
        return type(obj) == type([]) or type(obj) == type(())


def _is_string(obj):
    # Cover str and (Jython) unicode / java.lang.String without relying on a
    # single builtin being a valid isinstance() class argument.
    try:
        return isinstance(obj, basestring)
    except Exception:
        pass
    try:
        return isinstance(obj, str)
    except Exception:
        return type(obj) == type('')


def to_json(obj, indent=0):
    sp = ' ' * indent

    if obj is None:
        return 'null'

    # Booleans first, using identity so we never rely on `bool` being a usable
    # isinstance() class argument (it is not, under some WLST Jython builds).
    if obj is True:
        return 'true'
    if obj is False:
        return 'false'

    if _is_dict(obj):
        items = []
        for k in obj:
            items.append(
                sp + '  "' + str(k) + '": ' + to_json(obj[k], indent + 2)
            )
        return '{\n' + ',\n'.join(items) + '\n' + sp + '}'

    elif _is_list(obj):
        items = []
        for v in obj:
            items.append(to_json(v, indent + 2))
        return '[\n' + ',\n'.join(items) + '\n' + sp + ']'

    elif _is_string(obj):
        s = str(obj)
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        s = s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return '"' + s + '"'

    else:
        return str(obj)
