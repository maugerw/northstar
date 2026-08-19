package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"path"
	"regexp"
	"strconv"
	"strings"
)

// ---------------------------------------------------------------------------
// Console-facing lookup tables. These describe the WebLogic Admin Console's
// own UI and are genuinely constant across environments/domains -- they are
// not migration-specific data. (Mirrors DRIVER_INFO / TX_PROTOCOL_STEPS /
// SAF_SERVICE_TYPE_NOTE in gen_release_plan.py.)
// ---------------------------------------------------------------------------

type driverInfo struct {
	dbType string
	label  string
}

var DriverInfo = map[string]driverInfo{
	"oracle.jdbc.xa.client.OracleXADataSource": {
		dbType: "Oracle",
		label:  "Oracle's Driver (Thin XA) for Service connections; Versionless and Version Specific Connections",
	},
	"oracle.jdbc.OracleDriver": {
		dbType: "Oracle",
		label:  "Oracle's Driver (Thin) for Service connections (non-XA)",
	},
	"weblogic.jdbc.sqlserver.SQLServerDriver": {
		dbType: "MS SQL Server",
		label:  "Microsoft's MS SQL Server Driver (Type 4 XA)",
	},
}

var TxProtocolSteps = map[string]string{
	"TwoPhaseCommit": "leave **Supports Global Transactions** checked, and leave the radio on **Two-Phase Commit**",
	"OnePhaseCommit": "leave **Supports Global Transactions** checked, but set the radio to **One-Phase Commit**",
	"None":           "**uncheck** \"Supports Global Transactions\" entirely -- this data source does not use a global transaction protocol",
}

var SafServiceTypeNote = map[string]string{
	"Both":           "this agent both sends and receives",
	"Sending-only":   "this agent only sends (forwards outbound messages)",
	"Receiving-only": "this agent only receives (accepts imported messages)",
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

func loadExport(pathStr string) (*Export, error) {
	b, err := ioutil.ReadFile(pathStr)
	if err != nil {
		return nil, err
	}
	var e Export
	if err := json.Unmarshal(b, &e); err != nil {
		return nil, err
	}
	return &e, nil
}

var oracleURLRe1 = regexp.MustCompile(`^jdbc:oracle:thin:@//([^:/]+):(\d+)/(.+)$`)
var oracleURLRe2 = regexp.MustCompile(`^jdbc:oracle:thin:@([^:/]+):(\d+):(.+)$`)
var sqlServerURLRe = regexp.MustCompile(`^jdbc:weblogic:sqlserver://([^:;]+):(\d+)`)

type parsedConn struct {
	host, port, dbname string
}

// parseOracleURL extracts host/port/db-identifier from an Oracle thin URL,
// whichever of the two common styles was used. Returns ok=false if
// unrecognised (the generated doc falls back to leaving the field blank
// rather than guessing).
func parseOracleURL(url string) (parsedConn, bool) {
	if url == "" {
		return parsedConn{}, false
	}
	if m := oracleURLRe1.FindStringSubmatch(url); m != nil {
		return parsedConn{host: m[1], port: m[2], dbname: m[3]}, true
	}
	if m := oracleURLRe2.FindStringSubmatch(url); m != nil {
		return parsedConn{host: m[1], port: m[2], dbname: m[3]}, true
	}
	return parsedConn{}, false
}

// driverPropsDict returns an ordered list of (name,value) pairs — Go maps
// don't preserve order, and the original Python used OrderedDict, so we
// keep the slice-of-pairs shape used at the source (DriverProperties is
// already ordered as extracted).
func driverPropsMap(props []DriverProperty) map[string]string {
	m := make(map[string]string, len(props))
	for _, p := range props {
		m[p.Name] = p.Value
	}
	return m
}

func driverPropsJoined(props []DriverProperty) string {
	if len(props) == 0 {
		return "*(none)*"
	}
	parts := make([]string, 0, len(props))
	for _, p := range props {
		parts = append(parts, fmt.Sprintf("`%s=%s`", p.Name, p.Value))
	}
	return strings.Join(parts, ", ")
}

func sqlServerConnFields(ds JdbcDataSource) (host, port, dbname string) {
	props := driverPropsMap(ds.DriverProperties)
	host = props["serverName"]
	port = props["portNumber"]
	dbname = props["databaseName"]
	if host == "" || port == "" {
		if m := sqlServerURLRe.FindStringSubmatch(ds.URL); m != nil {
			if host == "" {
				host = m[1]
			}
			if port == "" {
				port = m[2]
			}
		}
	}
	return
}

// connFields returns (host, port, dbname) for the Connection Properties
// wizard page, regardless of driver family.
func connFields(ds JdbcDataSource) (host, port, dbname string) {
	driver := strings.ToLower(ds.DriverName)
	if strings.Contains(driver, "sqlserver") {
		return sqlServerConnFields(ds)
	}
	if parsed, ok := parseOracleURL(ds.URL); ok {
		return parsed.host, parsed.port, parsed.dbname
	}
	return "", "", ""
}

func dbUser(ds JdbcDataSource) string {
	return driverPropsMap(ds.DriverProperties)["user"]
}

func fmtTargets(targets []string) string {
	if len(targets) == 0 {
		return "tick nothing"
	}
	parts := make([]string, 0, len(targets))
	for _, t := range targets {
		parts = append(parts, fmt.Sprintf("`%s`", t))
	}
	return strings.Join(parts, ", ")
}

func boolYesNo(v bool) string {
	if v {
		return "Yes"
	}
	return "No"
}

var slugRe = regexp.MustCompile(`[^A-Za-z0-9_.-]+`)

func slug(name string) string {
	return slugRe.ReplaceAllString(name, "_")
}

// commonDirPath returns the deepest directory common to all given
// directory paths (POSIX paths only, mirroring gen_release_plan.py's
// Python-2.7-compatible os.path.commonpath replacement).
func commonDirPath(paths []string) string {
	if len(paths) == 0 {
		return ""
	}
	if len(paths) == 1 {
		return paths[0]
	}
	split := make([][]string, len(paths))
	minLen := -1
	for i, p := range paths {
		split[i] = strings.Split(p, "/")
		if minLen == -1 || len(split[i]) < minLen {
			minLen = len(split[i])
		}
	}
	var common []string
	for i := 0; i < minLen; i++ {
		part := split[0][i]
		allMatch := true
		for _, s := range split {
			if s[i] != part {
				allMatch = false
				break
			}
		}
		if allMatch {
			common = append(common, part)
		} else {
			break
		}
	}
	result := strings.Join(common, "/")
	if result == "" {
		return paths[0]
	}
	return result
}

// dirName mirrors os.path.dirname for POSIX paths in the export (paths in
// export.json are always Unix-style, regardless of the OS the CLI runs on
// — do NOT use filepath.Dir, which is OS-aware and would mangle a POSIX
// path on Windows).
func dirName(p string) string {
	return path.Dir(strings.ReplaceAll(p, "\\", "/"))
}

// ---------------------------------------------------------------------------
// pyInt/pyStr — format an optional numeric/string field exactly the way
// Python's "%s" % ds.get("field") renders it: the value if present, the
// literal text "None" if the key was missing/null. This preserves
// byte-for-byte parity with the original generator's output for every
// optional field.
// ---------------------------------------------------------------------------

func pyInt(v *int64) string {
	if v == nil {
		return "None"
	}
	return strconv.FormatInt(*v, 10)
}

func pyStr(v *string) string {
	if v == nil {
		return "None"
	}
	return *v
}

func fileExists(p string) bool {
	info, err := os.Stat(p)
	return err == nil && !info.IsDir()
}
