package main

import "sort"

// analysis.go — environment-derived facts used by both documents (counts,
// gap detection, the set of infra target names that would need
// substituting on another domain). Direct port of the analysis functions
// in gen_release_plan.py; keep the same semantics, including the same
// comments where they explain a non-obvious exclusion rule.

// infraTargetNames returns every distinct non-migratable, non-empty
// *domain-topology* target name referenced anywhere in the export -- this
// is the set a reader must remap if their target domain uses different
// server/cluster names than the source.
//
// Deliberately excludes subdeployment targets: a subdeployment's target is
// sometimes a real cluster (domain topology) but is often the name of a
// JMS server or SAF agent that *this same plan creates* in Phase 3/4 --
// those are not pre-existing domain names to remap, they're object names
// to create exactly as written, and Phase 5 already spells out the exact
// target to pick for each one. Mixing the two would incorrectly tell the
// reader a created object's name is something they need to "match their
// domain" against.
func infraTargetNames(e *Export) []string {
	names := map[string]bool{}
	addAll := func(targets []string) {
		for _, t := range targets {
			if !containsSubstr(t, "(migratable)") {
				names[t] = true
			}
		}
	}

	infra := e.Infrastructure
	for _, ds := range infra.JdbcDataSources {
		addAll(ds.Targets)
	}
	for _, st := range infra.PersistentStores {
		addAll(st.Targets)
	}
	for _, js := range infra.JmsServers {
		addAll(js.Targets)
	}
	for _, saf := range e.SafAgents {
		addAll(saf.Targets)
	}
	for _, mod := range e.JmsModules {
		addAll(mod.Targets)
	}
	for _, ad := range e.AdapterDeployments {
		addAll(ad.Targets)
	}

	// Strip out anything that is itself a JMS server or SAF agent name
	// created by this export (covers the case where a module's own
	// top-level target -- rare, but possible on some domains -- happens
	// to coincide with a created object name).
	created := map[string]bool{}
	for _, js := range infra.JmsServers {
		created[js.Name] = true
	}
	for _, saf := range e.SafAgents {
		created[saf.Name] = true
	}
	for n := range created {
		delete(names, n)
	}

	out := make([]string, 0, len(names))
	for n := range names {
		out = append(out, n)
	}
	sort.Strings(out)
	return out
}

func containsSubstr(s, substr string) bool {
	return len(s) >= len(substr) && (func() bool {
		for i := 0; i+len(substr) <= len(s); i++ {
			if s[i:i+len(substr)] == substr {
				return true
			}
		}
		return false
	})()
}

func knownDataSourceNames(e *Export) map[string]bool {
	m := make(map[string]bool)
	for _, ds := range e.Infrastructure.JdbcDataSources {
		m[ds.Name] = true
	}
	return m
}

type storeDataSourceDep struct {
	StoreName string
	DSName    string
}

// externalStoreDependencies returns JDBC stores whose dataSource isn't one
// of the data sources this export also captured -- i.e. a system/
// pre-existing data source the target domain must already have
// (SOALocalTxDataSource and friends).
func externalStoreDependencies(e *Export) []storeDataSourceDep {
	known := knownDataSourceNames(e)
	var deps []storeDataSourceDep
	for _, st := range e.Infrastructure.PersistentStores {
		if st.Type == "JDBCStore" && st.DataSource != nil && *st.DataSource != "" {
			dsName := *st.DataSource
			if !known[dsName] {
				deps = append(deps, storeDataSourceDep{StoreName: st.Name, DSName: dsName})
			}
		}
	}
	return deps
}

func extDepNamesOnly(deps []storeDataSourceDep) map[string]bool {
	m := make(map[string]bool, len(deps))
	for _, d := range deps {
		m[d.StoreName] = true
	}
	return m
}

func untargetedSafAgents(e *Export) []string {
	var out []string
	for _, s := range e.SafAgents {
		if len(s.Targets) == 0 {
			out = append(out, s.Name)
		}
	}
	return out
}

func fileStores(e *Export) []PersistentStore {
	var out []PersistentStore
	for _, s := range e.Infrastructure.PersistentStores {
		if s.Type == "FileStore" {
			out = append(out, s)
		}
	}
	return out
}

func jdbcStores(e *Export) []PersistentStore {
	var out []PersistentStore
	for _, s := range e.Infrastructure.PersistentStores {
		if s.Type == "JDBCStore" {
			out = append(out, s)
		}
	}
	return out
}

func targetedDataSources(ds []JdbcDataSource) []JdbcDataSource {
	var out []JdbcDataSource
	for _, d := range ds {
		if len(d.Targets) > 0 {
			out = append(out, d)
		}
	}
	return out
}

func untargetedDataSources(ds []JdbcDataSource) []JdbcDataSource {
	var out []JdbcDataSource
	for _, d := range ds {
		if len(d.Targets) == 0 {
			out = append(out, d)
		}
	}
	return out
}

func defaultTargetedCFs(modules []JmsModule) []string {
	var out []string
	for _, mod := range modules {
		for _, cf := range mod.ConnectionFactories {
			if cf.DefaultTargetingEnabled {
				out = append(out, cf.Name)
			}
		}
	}
	return out
}

type distDestNamePolicy struct {
	Name   string
	Policy string
}

func distributedDestinations(modules []JmsModule) []distDestNamePolicy {
	var out []distDestNamePolicy
	for _, mod := range modules {
		all := append([]Destination{}, mod.UniformDistributedQueues...)
		all = append(all, mod.DistributedQueues...)
		all = append(all, mod.UniformDistributedTopics...)
		all = append(all, mod.DistributedTopics...)
		for _, d := range all {
			policy := "*(default)*"
			if d.LoadBalancingPolicy != nil && *d.LoadBalancingPolicy != "" {
				policy = *d.LoadBalancingPolicy
			}
			out = append(out, distDestNamePolicy{Name: d.Name, Policy: policy})
		}
	}
	return out
}

func totalConnectionInstances(adapters []AdapterDeployment) int {
	n := 0
	for _, a := range adapters {
		n += len(a.ConnectionInstances)
	}
	return n
}

func joinBacktickNames(names []string) string {
	parts := make([]string, 0, len(names))
	for _, n := range names {
		parts = append(parts, "`"+n+"`")
	}
	return joinComma(parts)
}

func joinComma(parts []string) string {
	out := ""
	for i, p := range parts {
		if i > 0 {
			out += ", "
		}
		out += p
	}
	return out
}
