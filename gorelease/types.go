package main

// types.go — Go structs mirroring the export.json schema consumed by
// gen_release_plan.py. Numeric fields that gen_release_plan.py reads with
// dict.get() (and which can legitimately be absent/null in the source
// domain's config) are pointers, so a missing value renders as "None" via
// pyInt/pyStr, matching the Python script's %s formatting of a None value
// byte-for-byte. Fields always required by the extractor (name, etc.) are
// plain strings.

type Export struct {
	SafAgents          []SafAgent          `json:"safAgents"`
	AdapterDeployments []AdapterDeployment `json:"adapterDeployments"`
	JmsModules         []JmsModule         `json:"jmsModules"`
	Infrastructure     Infrastructure      `json:"infrastructure"`
}

type Infrastructure struct {
	MigratableTargets []MigratableTarget `json:"migratableTargets"`
	JdbcDataSources   []JdbcDataSource   `json:"jdbcDataSources"`
	PersistentStores  []PersistentStore  `json:"persistentStores"`
	JmsServers        []JmsServer        `json:"jmsServers"`
}

type MigratableTarget struct {
	Name string `json:"name"`
}

type DriverProperty struct {
	Name  string `json:"name"`
	Value string `json:"value"`
}

type JdbcDataSource struct {
	Name                       string           `json:"name"`
	URL                        string           `json:"url"`
	DriverName                 string           `json:"driverName"`
	TestTableName              string           `json:"testTableName"`
	TestConnectionsOnReserve   bool             `json:"testConnectionsOnReserve"`
	Targets                    []string         `json:"targets"`
	GlobalTransactionsProtocol string           `json:"globalTransactionsProtocol"`
	InitialCapacity            *int64           `json:"initialCapacity"`
	MaxCapacity                *int64           `json:"maxCapacity"`
	MinCapacity                *int64           `json:"minCapacity"`
	PasswordExported           bool             `json:"passwordExported"`
	JndiNames                  []string         `json:"jndiNames"`
	DriverProperties           []DriverProperty `json:"driverProperties"`
}

type PersistentStore struct {
	Name                   string   `json:"name"`
	Type                   string   `json:"type"` // "FileStore" | "JDBCStore"
	Directory              *string  `json:"directory"`
	SynchronousWritePolicy *string  `json:"synchronousWritePolicy"`
	DataSource             *string  `json:"dataSource"`
	PrefixName             *string  `json:"prefixName"`
	Targets                []string `json:"targets"`
}

type JmsServer struct {
	Name            string   `json:"name"`
	PersistentStore string   `json:"persistentStore"`
	Targets         []string `json:"targets"`
	BytesMaximum    *int64   `json:"bytesMaximum"`
	PagingDirectory *string  `json:"pagingDirectory"`
	MessagesMaximum *int64   `json:"messagesMaximum"`
}

type SafAgent struct {
	RetryDelayBase       *int64   `json:"retryDelayBase"`
	Name                 string   `json:"name"`
	ServiceType          string   `json:"serviceType"`
	RetryDelayMaximum    *int64   `json:"retryDelayMaximum"`
	RetryDelayMultiplier *int64   `json:"retryDelayMultiplier"`
	AcknowledgeInterval  *int64   `json:"acknowledgeInterval"`
	LoggingEnabled       bool     `json:"loggingEnabled"`
	Targets              []string `json:"targets"`
	WindowSize           *int64   `json:"windowSize"`
	Store                string   `json:"store"`
	TimeToLive           *int64   `json:"timeToLive"`
}

type AdapterDeployment struct {
	Targets             []string `json:"targets"`
	Name                string   `json:"name"`
	PlanPath            string   `json:"planPath"`
	SourcePath          string   `json:"sourcePath"`
	ConnectionInstances []string `json:"connectionInstances"`
}

// Destination covers queues, topics, and their uniform/plain distributed
// variants generically. The Python source treats all of these with
// dict.get() against a union of possible keys rather than distinct per-kind
// schemas, so one Go struct with every field optional mirrors that fidelity
// without inventing five near-identical types.
type Destination struct {
	Name                string  `json:"name"`
	JNDI                string  `json:"jndi"`
	Subdeployment       string  `json:"subdeployment"`
	ErrorDestination    *string `json:"errorDestination"`
	RedeliveryDelay     *int64  `json:"redeliveryDelay"`
	LoadBalancingPolicy *string `json:"loadBalancingPolicy"`
	ForwardingPolicy    *string `json:"forwardingPolicy"`
}

type ConnectionFactory struct {
	Name                    string  `json:"name"`
	JNDI                    string  `json:"jndi"`
	DefaultTargetingEnabled bool    `json:"defaultTargetingEnabled"`
	Subdeployment           *string `json:"subdeployment"`
}

type Template struct {
	Name            string `json:"name"`
	RedeliveryDelay *int64 `json:"redeliveryDelay"`
	RedeliveryLimit *int64 `json:"redeliveryLimit"`
	TimeToLive      *int64 `json:"timeToLive"`
	Priority        *int64 `json:"priority"`
}

type Quota struct {
	Name            string `json:"name"`
	BytesMaximum    *int64 `json:"bytesMaximum"`
	MessagesMaximum *int64 `json:"messagesMaximum"`
	Policy          string `json:"policy"`
	Shared          bool   `json:"shared"`
}

type DestinationKey struct {
	Name      string `json:"name"`
	Property  string `json:"property"`
	KeyType   string `json:"keyType"`
	Direction string `json:"direction"`
}

type ForeignDestinationOrCF struct {
	Name           string `json:"name"`
	LocalJNDIName  string `json:"localJNDIName"`
	RemoteJNDIName string `json:"remoteJNDIName"`
}

type ForeignServer struct {
	Name                       string                   `json:"name"`
	InitialContextFactory      string                   `json:"initialContextFactory"`
	ConnectionURL              string                   `json:"connectionURL"`
	DefaultTargetingEnabled    bool                     `json:"defaultTargetingEnabled"`
	ForeignDestinations        []ForeignDestinationOrCF `json:"foreignDestinations"`
	ForeignConnectionFactories []ForeignDestinationOrCF `json:"foreignConnectionFactories"`
}

type SafErrorHandling struct {
	Name             string  `json:"name"`
	Policy           string  `json:"policy"`
	ErrorDestination *string `json:"errorDestination"`
	LogFormat        *string `json:"logFormat"`
}

type Subdeployment struct {
	Name    string   `json:"name"`
	Targets []string `json:"targets"`
}

type JmsModule struct {
	Name                     string              `json:"name"`
	Targets                  []string            `json:"targets"`
	Subdeployments           []Subdeployment     `json:"subdeployments"`
	Queues                   []Destination       `json:"queues"`
	UniformDistributedQueues []Destination       `json:"uniformDistributedQueues"`
	DistributedQueues        []Destination       `json:"distributedQueues"`
	Topics                   []Destination       `json:"topics"`
	UniformDistributedTopics []Destination       `json:"uniformDistributedTopics"`
	DistributedTopics        []Destination       `json:"distributedTopics"`
	ConnectionFactories      []ConnectionFactory `json:"connectionFactories"`
	Templates                []Template          `json:"templates"`
	Quotas                   []Quota             `json:"quotas"`
	DestinationKeys          []DestinationKey    `json:"destinationKeys"`
	ForeignServers           []ForeignServer     `json:"foreignServers"`
	SafErrorHandlings        []SafErrorHandling  `json:"safErrorHandlings"`
}

func (m JmsModule) childCount() int {
	return len(m.Queues) + len(m.UniformDistributedQueues) + len(m.DistributedQueues) +
		len(m.Topics) + len(m.UniformDistributedTopics) + len(m.DistributedTopics) +
		len(m.ConnectionFactories) + len(m.Templates) + len(m.Quotas) +
		len(m.DestinationKeys) + len(m.ForeignServers) + len(m.SafErrorHandlings)
}
