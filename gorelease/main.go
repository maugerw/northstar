// Command gorelease generates the two release-plan documents (condensed +
// detailed) for a given environment's export.json, mirroring the hand-
// written gmx/dev plans byte-for-byte in structure — this is a Go port of
// extract/gen_release_plan.py for use where only a Go binary can run (e.g.
// a Windows AVD with no Python available).
//
// Usage:
//
//	gorelease environments/<domain>/<env>/export.json
//
// Writes, alongside the input file:
//
//	release-plan.md
//	release-plan-detailed.md
//
// Nothing in the output is hardcoded to a specific domain or environment:
// every name, host, port, driver, transaction protocol, pool size,
// queue/topic list, target set, and "untargeted / needs a password / needs
// a pre-existing dependency" flag is derived from the export.json passed
// in. Covers the full extract schema (queues, uniform/plain distributed
// queues, topics, uniform/plain distributed topics, templates, quotas,
// destination keys, foreign servers, connection factories, SAF error
// handlings), not just the object types gmx/dev happens to use.
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: gorelease environments/<domain>/<env>/export.json")
		os.Exit(1)
	}

	exportPath := os.Args[1]
	info, err := os.Stat(exportPath)
	if err != nil || info.IsDir() {
		fmt.Fprintf(os.Stderr, "error: %s not found\n", exportPath)
		os.Exit(1)
	}

	data, err := loadExport(exportPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: failed to parse %s: %v\n", exportPath, err)
		os.Exit(1)
	}

	// Infer domain/env from the conventional path
	// environments/<domain>/<env>/export.json (matches the Python script's
	// os.path.normpath + split on the OS separator; accept both slash
	// styles since a Windows AVD may receive the path with backslashes).
	domain, env := inferDomainEnv(exportPath)

	outDir := filepath.Dir(exportPath)
	condensedPath := filepath.Join(outDir, "release-plan.md")
	detailedPath := filepath.Join(outDir, "release-plan-detailed.md")

	condensed := renderCondensed(data, domain, env)
	detailed := renderDetailed(data, domain, env)

	if err := os.WriteFile(condensedPath, []byte(condensed), 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "error: failed to write %s: %v\n", condensedPath, err)
		os.Exit(1)
	}
	if err := os.WriteFile(detailedPath, []byte(detailed), 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "error: failed to write %s: %v\n", detailedPath, err)
		os.Exit(1)
	}

	fmt.Printf("Wrote %s (%d bytes)\n", condensedPath, len(condensed))
	fmt.Printf("Wrote %s (%d bytes)\n", detailedPath, len(detailed))
}

func inferDomainEnv(exportPath string) (domain, env string) {
	domain, env = "<domain>", "<env>"
	// Normalize to forward slashes and split directly -- do NOT route this
	// through filepath.Clean: on a Windows build, Clean converts every "/"
	// to the OS Separator ("\\"), which then makes a subsequent Split(...,
	// "/") find nothing to split on at all (invisible on Linux/macOS builds
	// where Separator is already "/" -- this is exactly the bug that showed
	// up on the AVD: <domain>/<env> placeholders instead of the real path
	// segments). A plain split on "/", skipping empty segments (from a
	// leading drive-letter root, a double slash, etc.), is all that's
	// needed here.
	normalized := strings.ReplaceAll(exportPath, "\\", "/")
	var parts []string
	for _, seg := range strings.Split(normalized, "/") {
		if seg != "" {
			parts = append(parts, seg)
		}
	}
	for i, p := range parts {
		if p == "environments" && i+2 < len(parts) {
			domain, env = parts[i+1], parts[i+2]
			return
		}
	}
	return
}
