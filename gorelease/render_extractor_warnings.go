package main

import (
	"fmt"
	"sort"
)

// render_extractor_warnings.go — shared body content for the final
// section of both documents: referential-integrity warnings the
// extractor itself found (and safely nulled) during export, plus any SAF
// Imported Destinations captured -- a real WebLogic object type this
// generator does not yet have a validated click-through procedure for
// (no export had populated it before). Always rendered, even when empty,
// so a warning can never go silently missing on some future messier
// domain -- the reader always sees that this was checked.
//
// Direct port of _render_extractor_warnings_body() in
// gen_release_plan.py; keep the two in sync if either changes.
func renderExtractorWarningsBody(e *Export) []string {
	var out []string
	a := func(s string) { out = append(out, s) }
	af := func(format string, args ...interface{}) { out = append(out, fmt.Sprintf(format, args...)) }

	dupes := duplicateJNDIDataSources(e)
	if len(dupes) > 0 {
		af("⚠️ **%d JNDI name(s) are claimed by more than one data source "+
			"in this export.** This is a real state of the source domain — "+
			"two distinct data sources (often pointing at different "+
			"hosts/databases) exporting the same JNDI string — not an "+
			"extraction error. Creating both on the target as written WILL "+
			"COLLIDE: whichever is created second either fails on a "+
			"duplicate JNDI or silently rebinds the JNDI away from the "+
			"first one. Anything that looks up this JNDI (an adapter "+
			"connection instance, a composite) is also ambiguous until this "+
			"is resolved on the source — confirm with the app owner which "+
			"data source is the real one before running Phase 1 for either, "+
			"or whether one is simply a leftover that should not be "+
			"migrated at all:\n", len(dupes))
		a("| JNDI Name | Claimed by |")
		a("|---|---|")
		for _, d := range dupes {
			af("| `%s` | %s |", d.JNDI, joinBacktickNames(d.Names))
		}
		a("")
	} else {
		a("No JNDI name collisions were found across the data sources in " +
			"this export — every JNDI name is claimed by exactly one data " +
			"source.\n")
	}

	warnings := e.ValidationWarnings
	if len(warnings) > 0 {
		af("⚠️ The extractor found %d referential-integrity issue(s) in the "+
			"source domain's config and nulled the dangling reference before "+
			"export (a safe default -- nothing broken is silently wired into "+
			"this plan). Review each one and confirm on the source what it "+
			"*should* reference before assuming this plan is complete:\n", len(warnings))
		for _, w := range warnings {
			af("- %s", w)
		}
		a("")
	} else {
		a("No referential-integrity warnings were reported by the extractor " +
			"for this export -- every destination/template/error-handling " +
			"reference captured here resolved to a real object on the source " +
			"domain.\n")
	}

	imported := e.SafImportedDestinations
	remoteContexts := e.SafRemoteContexts
	if len(imported) > 0 {
		af("⚠️ This export also captured %d SAF Imported Destination(s) -- a "+
			"real WebLogic object (Services → Messaging → Store-and-Forward "+
			"Agents → Imported Destinations) that this generator does not "+
			"yet have a validated click-through procedure for (no export has "+
			"populated this field before now, so no procedure has been "+
			"checked against a live console). Configure these manually on the "+
			"target using the data below, and treat this as a **known gap** "+
			"in the generator, not a completed phase:\n", len(imported))
		a("| Name | Local JNDI | Remote JNDI | Remote Context | Targets |")
		a("|---|---|---|---|---|")
		for _, d := range imported {
			targets := "*(none)*"
			if len(d.Targets) > 0 {
				targets = joinComma(d.Targets)
			}
			af("| `%s` | `%s` | `%s` | `%s` | %s |", d.Name, d.LocalJNDIName, d.RemoteJNDIName, d.RemoteContext, targets)
		}
		a("")
		citedSet := map[string]bool{}
		for _, d := range imported {
			if d.RemoteContext != "" {
				citedSet[d.RemoteContext] = true
			}
		}
		if len(citedSet) > 0 {
			cited := make([]string, 0, len(citedSet))
			for c := range citedSet {
				cited = append(cited, c)
			}
			sort.Strings(cited)
			a("**Remote Context connection details referenced above:**\n")
			for _, name := range cited {
				if rc, ok := remoteContexts[name]; ok {
					af("- `%s`: Initial Context Factory `%s`, Connection URL "+
						"`%s`, Provider URL `%s`", name, rc.InitialContextFactory, rc.ConnectionURL, rc.ProviderURL)
				} else {
					af("- `%s`: ⚠️ referenced by an imported destination "+
						"above but no matching entry in the export's "+
						"safRemoteContexts -- confirm this remote context "+
						"still exists on the source domain.", name)
				}
			}
		}
	} else {
		a("No SAF Imported Destinations were captured in this export.\n")
	}

	return out
}
