# Talend ESB: Routes, Data Services, REST, Talend Runtime, Microservices

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Scope: Talend Open Studio for ESB / Talend ESB / Data Services Platform /
Talend Cloud API Services / Studio 8 "Routes" and "Services" repository nodes.
Build-artifact mechanics shared with Jobs live in deployment-runtime.md; the
Studio IDE itself in studio.md; tXMLMap in tmap-expressions.md.

## Contents
- [Product map and version matrix](#product-map-and-version-matrix)
- [Core concepts](#core-concepts)
- [Talend Runtime (Karaf container)](#talend-runtime-karaf-container)
- [Infrastructure services (SL, SAM, STS, IAM, Event Logging)](#infrastructure-services-sl-sam-sts-iam-event-logging)
- [Deploying to Runtime: Studio, Karaf shell, TAC ESB Conductor, TMC](#deploying-to-runtime-studio-karaf-shell-tac-esb-conductor-tmc)
- [Mediation components (c*) catalog](#mediation-components-c-catalog)
- [Route runtime semantics](#route-runtime-semantics)
- [Data Services (SOAP)](#data-services-soap)
- [REST data services](#rest-data-services)
- [API Designer, API Tester, API Portal](#api-designer-api-tester-api-portal)
- [Microservices and Docker](#microservices-and-docker)
- [Security](#security)
- [Gotchas](#gotchas)
- [Sources](#sources)

## Product map and version matrix

| Name | What it is | Notes |
|---|---|---|
| Talend Open Studio for ESB (TOS ESB) | Free Studio with Mediation (Routes) + Data Services + a bundled Talend Runtime | OSS line ended with 8.0.1 (early 2024); no monthly R-releases. See versions-licensing.md |
| Talend ESB / Talend Data Services Platform | Subscription: Studio + Talend Runtime + TAC ESB Conductor + SL/SAM/STS/IAM/Event Logging | 5.x-7.3 |
| Talend Data Fabric 8.0 (ESB features) | Same, Studio 8 monthly R-releases; "Talend Runtime" shipped as `Talend-Runtime-V8.0.1.zip` (+ monthly patches) | Routes and Data Services also deployable to Talend Cloud Remote Engine |
| Talend Cloud API Services | Cloud edition: API Designer + API Tester + Studio (Routes/Data Services) + Remote Engine + TMC | Also "API Portal" (static docs site generator) |
| Talend Runtime | Apache Karaf OSGi container preconfigured with CXF, Camel, Talend job-controller, SL/SAM/STS add-ons | Folder `Runtime_ESBSE/container` (TOS) or `Talend-Runtime-*/container` |

Core framework versions (from release notes snippets):

| Talend Runtime / Studio | Karaf | CXF | Camel | Java |
|---|---|---|---|---|
| 7.3 | 4.2.x | 3.3.x | 2.24.x / 2.25.x (Camel 2) | 8 / 11 |
| 8.0.1 GA (2021) | 4.2.11 | 3.4.x | 3.11.1 (Camel 3) | 11 |
| 8.0.1 R2023-08 "core framework update" | 4.4.3 | 3.5.5 (one page says 3.5.6) | 3.20.6 | 11 / 17 |
| 8.0.1 R2025-01 | 4.4.x | 3.5.9 | 3.20.9 - FINAL monthly release of the Camel 3 generation (only CVE/blocker patches after: v2 Feb 2025, v3 Mar 2025) | 11 / 17 |
| 8.0.1 R2025-02 RT (Camel 4) and later | 4.4.6 | 4.1.0 | 4.8.1 (Camel 4, Spring Boot 3) | 17 required |

Rule: a Camel 4 Runtime (R2025-02+) only accepts Routes/Data Services built
with Studio R2025-02 or later; artifacts built with earlier Studios are
incompatible, and vice versa. Match Studio patch level to Runtime patch level.

## Core concepts

| Concept | Where in Studio 8 | What it generates / means |
|---|---|---|
| Route | Repository > `Routes` (Mediation perspective, "Route designer"); also visible in Integration perspective tree | A Java class extending `org.apache.camel.builder.RouteBuilder`; one Camel `from(...)` per start component. Built as OSGi bundle/KAR, Microservice jar, or Docker image |
| Routelet | Repository > `Routelets` | Reusable sub-route dropped into a Route like a component; starts with `cRouteletInput` and ends with `cRouteletOutput` (component names unverified). Compiled into the parent Route's bundle |
| Beans | Repository > `Code` > `Beans` | Plain Java classes compiled into the Route bundle; used by cBean, cBeanRegister, aggregation strategies, `${bean:...}` |
| Route Resources | Repository > `Route Resources` | Files (XSD, XSLT, properties, WSDL) bundled into the Route artifact and referenced from components |
| Service (Data Service, SOAP) | Repository > `Services` | WSDL-first: a Service node holds the WSDL; each port/operation is implemented by a Job (`tESBProviderRequest` -> ... -> `tESBProviderResponse` / `tESBProviderFault`) |
| REST data service | Ordinary Job under `Job Designs` starting with `tRESTRequest` | A Job exposed as JAX-RS endpoint via CXF; built as OSGi bundle (Runtime) or Microservice |
| REST API Definitions | Repository > `Metadata` > `REST API Definitions` | OAS 2.0 / OAS 3.0 / RAML imported from file, URL or Talend Cloud API Designer; drag onto a Job canvas -> preconfigured `tRESTRequest`; onto a Route canvas -> `cREST` (8.0 R2023-05+) |
| Job as web service (legacy) | Build Job > "Axis WebService (WAR)" | Deprecated Axis-based WAR export of a Job; superseded by tRESTRequest / Data Services. Removed from Studio 8 build types (unverified) |
| ESB Runtime Options | Right-click Service or REST Job > `ESB Runtime Options`; also `tRESTRequest`/`tESBConsumer` settings | Use Service Locator, Use Service Activity Monitor, Use Service Registry, Use Authentication, Use Authorization, Use Business Correlation, Log messages |
| Talend Runtime | Karaf container | Hosts Routes (Camel contexts), Data Service Jobs (CXF endpoints under `/services`), infrastructure services |
| ESB Conductor (TAC) | TAC > `ESB Conductor` | Deploys Route / Data Service / Generic OSGi Feature tasks from the Artifact Repository (Nexus/Artifactory) to registered Talend Runtime execution servers over JMX |
| Talend Cloud (TMC) | Management > Artifacts/Tasks | Artifact types `Job`, `Route`, `Data service`; Routes and Data services run on Remote Engine (v2.x+, approx 2020) as long-running tasks |

Studio preferences relevant to ESB: `Window > Preferences > Talend > ESB`
(Service Locator endpoint e.g. `localhost:2181`, SAM endpoint
`http://localhost:8040/services/MonitoringServiceSOAP`, STS endpoint, Service
Registry) used when running provider/consumer Jobs and Routes inside Studio.

## Talend Runtime (Karaf container)

Layout (`<Runtime>/container`):

```
container/
  bin/trun            # start Karaf with console (trun.bat on Windows)
  bin/start | stop | status | client   # background start/stop, status, ssh client
  etc/                # all *.cfg config files (Config Admin PIDs)
  deploy/             # hot-deploy folder (Felix FileInstall): drop .jar / .kar / feature .xml / blueprint .xml
  system/             # local Maven repository (offline source of all tesb-*, camel-*, cxf-* features)
  data/log/tesb.log   # main log (log4j2, configured in etc/org.ops4j.pax.logging.cfg)
  data/cache, data/tmp
  add-ons/            # sam, locator (zookeeper), sts, iam, el: scripts, DB DDL, samples
  lib/                # boot classpath, ext/ for JDBC drivers
```

Default ports (verify in `etc/*.cfg`):

| Port | Service | Config file / key |
|---|---|---|
| 8040 | HTTP (Pax Web / Jetty): CXF services under `/services` | `etc/org.ops4j.pax.web.cfg` `org.osgi.service.http.port=8040` (0 = pick a free port) |
| 9001 | HTTPS | `org.osgi.service.http.port.secure=9001`, `org.osgi.service.http.secure.enabled=true` |
| 8101 | Karaf SSH console | `etc/org.apache.karaf.shell.cfg` `sshPort=8101`, `sshHost=0.0.0.0` |
| 1099 | JMX RMI registry | `etc/org.apache.karaf.management.cfg` `rmiRegistryPort=1099` |
| 44444 | JMX RMI server | `rmiServerPort=44444`; TAC ESB Conductor uses 1099+44444 |
| 2181 | ZooKeeper (Service Locator server) | `add-ons`/`etc/org.talend.esb.locator*.cfg` (see below) |
| 8161 / 61616 | ActiveMQ web/openwire if embedded broker enabled | `etc/activemq.xml` / `tesb:start-activemq`? (unverified) |

CXF servlet context: `etc/org.apache.cxf.osgi.cfg` ->
`org.apache.cxf.servlet.context=/services`. All deployed SOAP/REST services are
listed at `http://host:8040/services` (CXF "Available services" page).

Default login (Talend Runtime 6.x-8.x): `tadmin` / `tadmin` in
`etc/users.properties` (Karaf's `karaf/karaf` is replaced). SSH:
`ssh -p 8101 tadmin@localhost` or `bin/client -u tadmin`.

Karaf shell commands you actually use:

```
# bundles / features
bundle:list [-t 0]            # -t 0 shows all incl. system bundles
bundle:install -s file:///path/MyJob_0.1.jar
bundle:start|stop|uninstall <id>
bundle:diag <id>              # why a bundle is not Active (unresolved imports)
feature:repo-add mvn:org.example/MyRoute-feature/0.1/xml   # feature descriptor from Maven repo
feature:repo-add file:///path/MyRoute-feature-0.1.xml
feature:install MyRoute-feature
feature:list [-i]             # -i installed only
kar:install file:///path/MyRoute_0.1.kar ; kar:list ; kar:uninstall <name>
# camel
camel:context-list ; camel:route-list ; camel:route-info <routeId> ; camel:route-stop|start <routeId>
# talend esb add-ons
tesb:start-all                # all infrastructure services (Locator, SAM, STS, EL, ...)
tesb:start-locator | tesb:stop-locator
tesb:start-sam     | tesb:stop-sam
tesb:start-sts     | tesb:stop-sts
tesb:start-el-default | tesb:stop-el-default    # Event Logging (there is no plain tesb:start-el)
tesb:start-iam?    # IAM has its own start-* command in 7.x (exact name unverified; see IAM below)
# logging / admin
log:tail ; log:display ; log:set DEBUG org.apache.camel ; log:exception-display
config:list "(service.pid=org.ops4j.pax.web)" ; config:edit <pid> ; config:property-set k v ; config:update
jaas:realm-list ; jaas:realm-manage --realm karaf ; jaas:user-list ; jaas:user-add u p ; jaas:role-add u admin ; jaas:update
system:shutdown  (or shutdown -f) ; halt
```

Karaf starts non-core bundles in the background: the console prompt appears
before `tesb:*` and `camel:*` commands exist; wait or re-run.

Features of note (names approximate; confirm with `feature:list | grep tesb`):
`tesb-job-api`, `tesb-job-controller` (runs Talend Jobs as OSGi services),
`tesb-xml`, `tesb-sam-agent`, `tesb-sam-server`, `tesb-locator-client`,
`tesb-zookeeper-server`, `tesb-sts`, `tesb-derby-starter`/`tesb-h2`,
`tesb-el-default`, `tesb-cxf-*`, plus standard `camel-*`, `cxf-*`,
`activemq-*`, `jolokia`, `hawtio` (hawtio not bundled; install from Maven if
online; unverified).

Hot deploy: `etc/org.apache.felix.fileinstall-deploy.cfg`
(`felix.fileinstall.dir=deploy`, `felix.fileinstall.poll=1000`). A failing
bundle is retried on every poll -> log spam; delete the file to stop it.

Offline feature install: `etc/org.ops4j.pax.url.mvn.cfg`
(`org.ops4j.pax.url.mvn.repositories=...`,
`org.ops4j.pax.url.mvn.localRepository=${karaf.home}/system`,
`org.ops4j.pax.url.mvn.defaultRepositories`). Anything not in `system/` is
fetched from the listed remote repos (Talend Nexus / Maven Central); air-gapped
containers must have the feature's jars pre-populated in `system/` or in the
KAR.

Context overrides for deployed Routes/Data Services: create
`etc/<ArtifactName>.cfg` (PID = bundle symbolic name / Route name) with
`contextVar=value` lines; the job-controller injects them at start and on
Config Admin update (unverified exact PID naming; documented as "configuring
context" in the ESB Container Administration Guide).

JMX / Jolokia: Karaf exposes `org.apache.karaf:type=feature,...`,
`org.apache.camel:context=...` MBeans on 1099/44444; TAC and the Karaf
`jolokia` feature (REST `http://host:8040/jolokia`) read them (Jolokia path
unverified).

Clustering: Talend Runtime has no built-in cluster. Pattern = N identical
containers behind an HTTP load balancer for REST/SOAP, plus Service Locator
(ZooKeeper ensemble) so consumers discover live provider endpoints; stateful
Camel patterns (aggregate, idempotent) need a shared repository (JDBC/Hazelcast)
or you pin them to one node. Karaf Cellar is not shipped (unverified).

## Infrastructure services (SL, SAM, STS, IAM, Event Logging)

| Service | Purpose | Start | Config (container/etc) | Notes |
|---|---|---|---|---|
| Service Locator (SL) | Endpoint registry/discovery on ZooKeeper; providers register on start, consumers resolve `locator://` addresses; load-balancing across registered endpoints | `tesb:start-locator` (embedded ZooKeeper 2181) | `org.talend.esb.locator.cfg`: `locator.endpoints=localhost:2181` (comma list for ensemble), `connection.timeout`, `session.timeout`, `endpoint.prefix`, `authentication.name/password` (SL ACL) | Consumer side: "Use Service Locator" replaces the endpoint with a locator URL; "Custom Properties" table filters by name=value properties published by the provider. Studio-side ZooKeeper address in Preferences > Talend > ESB |
| Service Activity Monitoring (SAM) | Agent in provider/consumer captures REQ/RESP/FAULT events (+ optional message content) and posts them to the SAM server, which writes a DB and exposes a REST/UI query API; TAC "Service Activity Monitoring" page | `tesb:start-sam` (server + H2/Derby by default) | Agent `org.talend.esb.sam.agent.cfg`: `service.url=http://localhost:8040/services/MonitoringServiceSOAP`, `collector.scheduler.interval`, `collector.maxEventsPerCall`, `log.messageContent`, `log.filter.*`, `log.enforceMessageIDTransfer`. Server `org.talend.esb.sam.server.cfg` + datasource `org.talend.esb.datasource.<db>.cfg` (h2/derby/mysql/postgresql/oracle/sqlserver/db2) | Tables `EVENTS` and `EVENTS_CUSTOMINFO`; DDL per DB under `add-ons/sam/db/` (unverified path). Disabled in the UI when "Use Service Registry" is checked. cCXF Dataformat RAW is NOT monitored; CXF_MESSAGE is |
| Security Token Service (STS) | WS-Trust STS issuing SAML tokens; provider validates SAML (Use Authentication = SAML Token), consumer obtains token with username/password or X.509 | `tesb:start-sts` | STS WSDL `http://host:8040/services/SecurityTokenService/UT` and `/X509`; client cfg `org.talend.esb.job.client.sts.cfg`, service cfg `org.talend.esb.job.service.cfg` (signature/encryption properties); sample keystores `etc/keystores/{clientstore,servicestore,stsstore}.jks` (file names unverified) | Authenticates against Karaf JAAS (`users.properties`) by default; 7.x+ can delegate to IAM/Syncope |
| Identity and Access Management (IAM) | Apache Syncope based user/role store used by Authentication (UsernameToken/HTTP Basic) and Authorization (role-based access to services/operations) in 7.x+ | 7.x: separate `tesb:start-*` command / separate IAM web app deployed into Runtime or Tomcat (exact command unverified; earlier 6.x "Talend Authorization" was XACML based) | `org.talend.esb.*auth*.cfg` (unverified) | "Use Authorization" in ESB Runtime Options requires roles defined in IAM. Not available in Open Studio |
| Event Logging (EL) | Ships container/OSGi log events to a central store (7.x: Talend LogServer = Elasticsearch/Kibana via Logstash; earlier: JMS + DB) | `tesb:start-el-default` | `org.talend.esb.eventlogging*.cfg` (unverified) | Visible in TAC `Logging` page |
| Service Registry (Enterprise only) | Stores WSDL/WS-Policy and does dynamic endpoint lookup/policy enforcement at runtime | separate install | - | Checking "Use Service Registry" hides Use Service Locator and disables SAM and Business Correlation in the component UI. Deprecated/removed in 7.x-8.0 (unverified) |

Business Correlation: with "Use Business Correlation" the provider reads a
correlation ID from the request header (SOAP header / HTTP header named
`CorrelationID`, unverified) or generates one, stores it in a component
variable (`globalMap.get("tESBProviderRequest_1_CORRELATION_ID")`, unverified)
and SAM records it so chained calls can be grouped.

## Deploying to Runtime: Studio, Karaf shell, TAC ESB Conductor, TMC

Build types (right-click Route > `Build Route`; Service > `Build Service`? and
Job > `Build Job` with ESB components):

| Build type | Output | Target |
|---|---|---|
| OSGi Bundle For ESB | Route: `<Route>_<ver>.kar` (KAR = bundle + `feature.xml`); Job/Data Service: `<Job>_<ver>.jar` OSGi bundle (or KAR for a Service node; verify extension in your release) | Talend Runtime (`kar:install`, `bundle:install`, `deploy/`, TAC ESB Conductor) |
| Microservice (Spring Boot) | `<Name>_<ver>.jar` fat jar with embedded Tomcat/Camel | `java -jar`, Talend Cloud Remote Engine, Kubernetes |
| Docker Image | Image pushed to local daemon/registry | Container platforms |
| Standalone Job (Jobs only) | zip with shell/bat launchers | Not for Routes; a Job containing tRESTRequest can run standalone and listens on its REST Endpoint URL |

Studio `Publish` (right-click Route/Service/Job > `Publish`): uploads the
built artifact + feature descriptor to the Artifact Repository configured in
Studio (Preferences > Talend > `Artifact Repository`? or via TAC project
settings): Nexus 2/3 or Artifactory, repos `releases` / `snapshots`, groupId
default `org.example` (unverified), artifactId = item name, version = item
version, "Publish as Snapshot" checkbox. `Publish to Cloud` targets TMC.

Manual Karaf deployment:

```
# KAR (route or service built as OSGi bundle for ESB)
kar:install file:///opt/artifacts/CustomerRoute_0.1.kar
# plain bundle (job with tRESTRequest / tESBProviderRequest)
bundle:install -s file:///opt/artifacts/GetCustomer_0.1.jar
# from Nexus (needs etc/org.ops4j.pax.url.mvn.cfg repositories to include it)
feature:repo-add mvn:org.example/CustomerRoute-feature/0.1/xml
feature:install CustomerRoute-feature
# verify
camel:route-list            # routes Started?
bundle:list | grep Customer # Active?
http://localhost:8040/services   # endpoint listed?
```

TAC ESB Conductor (on-prem subscription):
1. `Configuration > Artifact repository`: Nexus/Artifactory URL + creds.
2. `Servers`: add execution server, check `Talend Runtime`; fields `Host`,
   `Instance` (e.g. `trun`), `Admin console port 8101`, `MGMT-Server port 44444`,
   `MGMT-Reg port 1099`, credentials `tadmin/tadmin` (labels approximate).
3. `ESB Conductor > Add`: task types `Route`, `Data Service`, `Generic OSGi
   Feature`; pick Group/Artifact/Version from the repository browser, the
   Runtime server, optional context; actions `Deploy`, `Start`, `Stop`,
   `Undeploy`, `Redeploy`/`Update` to a new version. TAC drives Karaf's
   `feature:repo-add` + `feature:install` via JMX, so the Runtime must be able
   to reach the artifact repository itself.

Talend Cloud (TMC): Studio `Publish to Cloud` creates a `Route` / `Data
service` artifact; `Management > Tasks > Add task` picks the artifact, a
Remote Engine (not a Cloud Engine), context values, and runs it as a
continuously running task (microservice); REST port exposed on the engine
host. Supported from Remote Engine v2.x (approx 2020) and TMC "API Services"
or "Data Fabric" licenses (unverified details).

## Mediation components (c*) catalog

Palette families: Connectivity, Context, Core, Custom (cBean), Exception,
Messaging, Miscellaneous, Routing, Transformation, plus `Apache CXF`
(cCXF, cREST, cSOAP). Every Java-typed field is a Java expression: string
literals need quotes, `context.var` works everywhere.

### Connectivity / endpoints

| Component | Camel URI / DSL | Purpose | Key settings | Notes |
|---|---|---|---|---|
| cTalendJob | `talend:` (camel-talendjob) | Invoke a Talend Job (synchronously) as a processor; body passed to the Job's `tRouteInput`, Job's `tRouteOutput` body becomes new exchange body, `tRouteFault` raises an exception in the route | `Repository` (pick Job + version `Latest`) or `External` (job class name, jar); `Context`; `Context Param` table (name/value, values are Java expressions); Advanced: `Propagate Header` (route headers -> Job context vars, as Strings only), `Fast Job Invocation` (reuse job instance; incompatible with some Propagate Header cases), `Use job's own context values`? (unverified) | Job must contain tRouteInput/tRouteOutput to exchange data; otherwise it just runs. Headers arrive as Strings; put complex objects in the body. A Job referenced by Repository is compiled into the Route bundle |
| cFile | `file:<dir>?noop=&delete=&move=&moveFailed=&include=&exclude=&recursive=&fileName=&charset=&delay=&initialDelay=&readLock=` | Poll a directory (consumer) or write files (producer) | `Path`, `Encoding`, `Noop`, `Delete`, `Move to`, `Move failed`, `Include/Exclude regex`, `Recursive`, `File name` (producer), `Flatten`, `Auto create`, `Advanced: Read lock` | Body is `GenericFile`; add cConvertBodyTo String before string processing. `${header.CamelFileName}` holds the file name |
| cFtp | `ftp:` / `sftp:` / `ftps:` `user@host:port/dir?password=&passiveMode=&binary=&delete=&move=&disconnect=&privateKeyFile=&knownHostsFile=` | FTP/SFTP consumer or producer | `Protocol`, `Server`, `Port`, `Username/Password`, `Path`, `Private key` (SFTP), `Passive mode`, `Binary`, same file options as cFile | Idle connections: `disconnect=true` |
| cHttp | `http:` (Camel 2: `http4:`) `//host/path?httpMethod=&bridgeEndpoint=true&throwExceptionOnFailure=` | HTTP client (producer only; use cREST/cJetty for server) | `URI`, `Method` (GET/POST/PUT/DELETE/PATCH), `Headers` table, `Body`?, `Use Proxy`, `Authentication` (Basic), `Throw exception on failure` | Response code in `${header.CamelHttpResponseCode}`. Camel 4 renamed many http options; check generated code |
| cCXF | `cxf:` (`cxf:bean:` or `cxf://address?wsdlURL=&serviceName=&portName=&dataFormat=`) | SOAP endpoint: consumer (start, service provider) or producer (call a SOAP service) | `WSDL File` or `Service class` (`Service Type`: wsdlURL / serviceClass); `Service Name` (QName), `Port Name`, `Address`, `Dataformat` = `PAYLOAD` (SOAP body as `CxfPayload`), `MESSAGE`/`RAW` (raw stream, no SAM), `POJO` (JAXB generated classes), `CXF_MESSAGE` (raw with SAM support); `Use Service Locator`, `Use Service Activity Monitor`, `Use Authentication` (WS-Security UsernameToken / SAML Token via STS / HTTP Basic), `Use Authorization`, `Use Business Correlation`, `Log messages`; Advanced: `Properties` (CXF properties table), `MTOM`, `WS-Addressing`, `WS-RM`? | In Studio default address `http://localhost:8090/...`; in Runtime address becomes relative `/services/...` on 8040. Response body in PAYLOAD is `CxfPayload<SoapHeader>`; convert with cConvertBodyTo `org.w3c.dom.Document` or `String` |
| cREST | `cxfrs:` (`cxfrs://http://host:port/path?...`) | JAX-RS endpoint: consumer (provider Route) or producer (call REST) | `Endpoint` (defaults 8090 in Studio, 8040 Runtime, 8065 Microservice), `API Definition` = Built-In / Repository (REST API Definitions), `Type` = Manual (`REST API Mapping` table: Verb, URI Pattern, Consumes, Produces, Output flow?) ; `Use Service Locator`, `Use SAM`, `Use Authentication` (Basic/Digest/SAML/OAuth2? unverified), `Enable CORS`?, `Log messages`; Advanced: `Convert JSON to XML`?, `Streaming` | Request body String/InputStream; path params as headers named after `{param}`; HTTP method `${header.CamelHttpMethod}`, path `${header.CamelHttpPath}`; set `CamelHttpResponseCode` header to control status |
| cSOAP | `soap` dataformat (marshal/unmarshal) | Legacy SOAP dataformat for POJO <-> SOAP envelope | `Context path` (JAXB package), `Element name strategy` | Deprecated; cCXF covers nearly all cases |
| cJMS | `jms:queue:NAME` / `jms:topic:NAME` `?connectionFactory=#id&concurrentConsumers=&selector=&transacted=&disableReplyTo=&requestTimeout=` | JMS consumer/producer | `Type` queue/topic, `Destination`, `ConnectionFactory` (bean id from cJMSConnectionFactory / cMQConnectionFactory), `Advanced: Durable subscription`, `Client ID`, `Selector`, `Transacted`, `Concurrent consumers` | Request-reply: InOut pattern + `JMSReplyTo`; to fire-and-forget use cSetExchangePattern InOnly |
| cJMSConnectionFactory | registers a `javax.jms.ConnectionFactory` bean | Define a broker connection for cJMS | `MQ Server` = ActiveMQ (`Broker URI tcp://host:61616`, `Use PooledConnectionFactory`, `Max connections`), `WebSphere MQ` (host, port, queue manager, channel, transport type), `Other` (custom class + properties); `Use transaction` | Name shown in cJMS `ConnectionFactory` dropdown |
| cMQConnectionFactory | same as above, older name (5.x-6.x) | | | Replaced by cJMSConnectionFactory; both may appear in old projects |
| cAMQP | `amqp:queue:NAME` | AMQP 1.0 (Qpid JMS) consumer/producer | `Destination`, `Type`, `ConnectionFactory` (cAMQPConnectionFactory, unverified) | Used for Azure Service Bus / ActiveMQ Artemis / RabbitMQ with AMQP 1.0 plugin |
| cKafka | `kafka:TOPIC?brokers=host:9092&groupId=&autoOffsetReset=&securityProtocol=&saslMechanism=&maxPollRecords=` | Kafka consumer/producer | `Topic`, `Brokers`, `Group Id`, `Auto Offset Reset`, `Consumers count`, `Key/Value serializer`, `Security` (SSL/SASL settings table) | Body String by default; key in `${header.kafka.KEY}` (Camel header `kafka.KEY`); offset commit per `autoCommitEnable` |
| cMQTT | Camel 2: `mqtt:`; Camel 3: `paho:TOPIC?brokerUrl=tcp://host:1883&qos=&clientId=`; Camel 4: `paho-mqtt5:` | MQTT publish/subscribe | `Broker URL`, `Topic`, `QoS`, `Client ID`, `Username/Password`, `Clean session`, `Retain` | Component implementation changed across Camel versions; rebuild after Runtime upgrade |
| cMail | `smtp(s)://host:port?username=&password=&to=&from=&subject=` / `imap(s)://` / `pop3(s)://` | Send or poll mail | `Protocol`, `Host`, `Port`, `Username/Password`, `To/From/CC/Subject`, `Content type`, consumer: `Delete`, `Unseen`, `Folder` | Body = mail text; attachments via `exchange.getIn().getAttachments()` (Camel 3: `AttachmentMessage`) |
| cMessagingEndpoint | any Camel URI | Generic endpoint for components without a dedicated c* (e.g. `jetty:`, `netty:`, `sql:`, `jdbc:`, `log:`, `mock:`, `stream:out`, `activemq:`, `aws2-s3:`, `salesforce:`) | `URI` (Java String), Advanced: `Dependencies` (Camel component names to add to the bundle, e.g. `camel-sql`) | The most common escape hatch; must add the Camel component dependency or the bundle fails with "No component found with scheme" |
| cDirect | `direct:NAME` | Synchronous in-memory link between routes in the same CamelContext | `Name` | Standard way to link a cMessageRouter `when` output to a sub-route |
| cDirectVM | `direct-vm:NAME` | Synchronous link across CamelContexts in the same JVM | `Name` | REMOVED in Camel 4 (Runtime R2025-02+): replace with cDirect or cSEDA (unverified Studio handling) |
| cSEDA | `seda:NAME?concurrentConsumers=&size=&blockWhenFull=&waitForTaskToComplete=` | Asynchronous in-memory queue within a CamelContext | `Name`, `Concurrent consumers`, `Queue size`, `Wait for task to complete` | Unbounded by default -> memory; set `size` |
| cVM | `vm:NAME` | Asynchronous queue across CamelContexts in a JVM | same as cSEDA | REMOVED in Camel 4 |
| cTimer | `timer://NAME?period=&repeatCount=&delay=&fixedRate=&time=` | Start a route on a schedule (simple) | `Name`, `Period` (ms), `Repeat` (0 = forever), `Delay`, `Fixed rate`, `Daemon` | For cron use cMessagingEndpoint `quartz://group/name?cron=0+0/5+*+*+*+?` (camel-quartz) |

### Core / processing

| Component | DSL | Purpose | Key settings | Notes |
|---|---|---|---|---|
| cProcessor | `.process(new Processor(){ public void process(Exchange exchange) {...} })` | Arbitrary Java on the exchange | `Code` (Java body; `exchange` in scope) | Camel 3+: prefer `exchange.getMessage()` over `getOut()`; `exchange.getIn().getBody(String.class)` converts |
| cJavaDSLProcessor | raw Java DSL fragment inserted into the route chain | Anything the palette lacks (`.enrich("direct:x", strategy)`, `.pollEnrich(...)`, `.marshal().json()`, `.unmarshal().jacksonXml()`, `.to("sql:...")`, `.transacted()`) | `Code` (starts with `.`) | There is no cContentEnricher / cMarshal component in the palette (unverified); use this |
| cBean | `.bean(beanRef or class, "method")` | Call a method of a Repository Bean or registered bean | `Reference` (registered bean id) or `New instance` (bean class), `Method` | Return value becomes body unless method is void |
| cBeanRegister | registers bean in Camel registry at context start | Make a bean available by id (`#id`, `${bean:id}`, strategies) | `Id`, `Class`, `Arguments` (constructor), `Properties` (setters) | Needed for cAggregate/cSplitter strategies, cJMS connection factories not created via dedicated component, idempotent repos |
| cConfig | Spring/Blueprint `<bean>` XML or Java config | Define arbitrary Spring beans / Camel config (e.g. `PropertiesComponent`, DataSource, custom `CamelContext` settings) | `Code` | In 8.0 Spring XML is wrapped into the generated Blueprint/Spring context (unverified) |
| cSetBody | `.setBody(expr)` | Replace message body | `Language` (Constant/Simple/Header/Property/XPath/JSONPath/Groovy/Bean/EL/MVEL/OGNL/SpEL/SQL/XQuery...), `Expression` | Constant with Java: `"literal"` |
| cSetHeader | `.setHeader(name, expr)` | Set one or more headers | `Headers` table: Name, Language, Value | Header names are case-sensitive; HTTP components map headers to HTTP headers on output (filter with `HeaderFilterStrategy`) |
| cSetProperty | `.setProperty(name, expr)` | Set exchange properties (survive across splits/aggregates differently from headers) | `Properties` table | Read with `${exchangeProperty.X}` |
| cSetExchangePattern | `.setExchangePattern(ExchangePattern.InOnly|InOut|RobustInOnly)` | Force request-reply or one-way semantics for the next endpoint | `Pattern` | Use before cJMS to avoid waiting for a reply |
| cConvertBodyTo | `.convertBodyTo(Class, charset)` | Type conversion via Camel type converters | `Type` (`String`, `byte[]`, `org.w3c.dom.Document`, `java.io.InputStream`, custom class), `Charset` | Streams can be read once: convert to String/byte[] before wiretap/multicast or enable stream caching |
| cLog | `.log(level, "msg ${body}")` or `log:` endpoint | Log with Simple-language message | `Level`, `Message` (Simple), `Logger name`, `Marker`; Advanced: `Show body/headers/exchange pattern`, `Multiline` | Logs to `tesb.log` under logger `route.<RouteName>`? (unverified) |
| cStop | `.stop()` | Stop routing this exchange | - | After cStop nothing downstream executes; still returns reply to InOut caller |
| cDelayer | `.delay(ms)` | Pause per message | `Time` (ms, Java expr), `Async delayed` | |
| cThrottler | `.throttle(n).timePeriodMillis(ms)` | Limit messages per period | `Maximum requests`, `Time period (ms)`, `Async delayed`, `Reject execution` | Camel 4 throttler semantics changed (concurrent requests mode vs total requests) |
| cLoop | `.loop(n)` or `.loop(expr)` / `.loopDoWhile(pred)` | Repeat downstream n times | `Count` or `Expression`, `Copy` (each iteration on a copy) | `${exchangeProperty.CamelLoopIndex}` |
| cPipesAndFilters | `.pipeline(uris...)` | Chain endpoints explicitly | `URIs` list | Rarely needed; default Camel route IS a pipeline |
| cValidate | `.validate(predicate)` | Throw `PredicateValidationException` when predicate false | `Language`, `Expression` | For XSD validation use cMessagingEndpoint `validator:classpath:x.xsd` |

### Routing (EIP)

| Component | DSL | Purpose | Key settings | Notes |
|---|---|---|---|---|
| cMessageRouter | `.choice().when(p1)...when(p2)...otherwise()...end()` | Content-based router | Output links: `when` (each with `Type`/language: bean, constant, correlation, el, groovy, header, jsonpath, jxpath, mvel, ognl, php, property, python, ruby, simple, Spel, sql, xpath, xquery; and `Expression`), `otherwise`; `endChoice()` checkbox on the when link | Evaluated in link order; first match wins; messages matching no `when` and with no `otherwise` are dropped. Put only a cDirect/mock endpoint after each `when`/`otherwise` and continue in a sub-route; if a cMessageFilter/cLoadBalancer etc. directly follows a `when`, compile error -> check `endChoice()` |
| cMessageFilter | `.filter(pred)` | Drop messages not matching | `Type`/`Expression` | Pass-through of matched messages only |
| cSplitter | `.split(expr).streaming().parallelProcessing().aggregationStrategy(bean)` | Split body into sub-messages (tokenize, XPath, Simple `${body}` over a List, `tokenize("\n")`) | `Type`/`Expression`, `Use Strategy` (aggregation strategy bean to combine replies: in split order, or arrival order if streaming), `Parallel Processing` (caller waits for all), `Use Streaming`, `Stop on Exception`, `Timeout`, `Thread pool` | Each sub-message gets properties `CamelSplitIndex`, `CamelSplitSize`, `CamelSplitComplete`; without strategy the original message continues after the split (Camel default) |
| cAggregate | `.aggregate(correlationExpr, strategy).completionSize(n).completionTimeout(ms).completionPredicate(p).completionInterval().eagerCheckCompletion()` | Combine N messages into one | `Correlation Expression` (Type/Expression), `Strategy` (bean class implementing `AggregationStrategy`, or registered id), `Completion conditions`: `Number of messages` (default 3), `Timeout`, `Interval`, `Predicate`, `Eager check`, `Ignore invalid correlation keys`, `Close correlation key on completion`, `Group exchanges`; Advanced: `Persistence` (JDBC/Hazelcast/Leveldb repository id, recover) | Default repo is in-memory: lost on restart and not shared across nodes |
| cMulticast | `.multicast(strategy).parallelProcessing().to(a,b,c)` | Send a copy to each output link | `Use Strategy`, `Parallel Processing`, `Stop on Exception`, `Timeout`, `Streaming` | Body streams must be cached/converted first |
| cRecipientList | `.recipientList(expr, delimiter)` | Dynamic list of endpoints from an expression | `Type`/`Expression` (e.g. header with `direct:a,direct:b`), `Delimiter`, `Parallel`, `Strategy`, `Ignore invalid endpoints` | |
| cDynamicRouter | `.dynamicRouter(expr)` | Re-evaluates expression after each hop until it returns null | `Type`/`Expression` (usually bean) | Bean must return null to end; otherwise infinite loop |
| cRoutingSlip | `.routingSlip(expr, delimiter)` | Static list of hops computed once | `Type`/`Expression`, `Delimiter` | |
| cLoadBalancer | `.loadBalance().roundRobin()|random()|sticky(expr)|topic()|failover(n, inheritErrorHandler, roundRobin, exceptions...)|weighted(roundRobin, "4,2")|custom(bean)` | Distribute across output links | `Strategy`: Round robin, Random, Sticky (correlation expression), Topic, Failover (`Maximum failover attempts`, `Round robin`, `Inherit error handler`, `Exceptions` list), Weighted (`Round robin`, `Distribution ratio`), Custom | Failover + error handler interplay: set `inheritErrorHandler=false` to let failover try the next endpoint immediately |
| cIdempotentConsumer | `.idempotentConsumer(expr, repo)` | Skip duplicates by key | `Type`/`Expression` (message id), `Repository`: Memory (`Cache size`), File (`File store`, `Cache size`), JDBC/Hazelcast via registered bean; `Eager`, `Skip duplicate`, `Remove on failure` | Memory repo is per JVM; use JDBC repo across cluster |
| cWireTap | `.wireTap(uri).copy()` | Fire-and-forget copy to another endpoint | `URI`, `Copy`, `New exchange` (Populate body/headers with expressions) | Runs on separate thread; streams must be converted |
| (no cResequencer) | `.resequence(expr).batch()` / `.stream()` | Reorder messages | - | No palette component as of 7.x/8.0 (unverified); use cJavaDSLProcessor |

### Exception handling

| Component | DSL | Purpose | Key settings | Notes |
|---|---|---|---|---|
| cErrorHandler | `errorHandler(defaultErrorHandler()|deadLetterChannel(uri)|loggingErrorHandler()|noErrorHandler())` | Route-level (or global when placed unconnected) error handler | `Type`: `Default Handler` (no DLQ, exception returned to caller), `Dead Letter` (`Dead Letter URI`, `Use Original Message`), `Logging` (`Log name`, `Level`), `None`; redelivery: `Set Maximum Redeliveries`, `Maximum Redeliveries` (Camel default 5 here configurable), `Set Redelivery Delay`/`Initial redelivery delay` (ms), `Use exponential backoff`/`Back off multiplier`/`Maximum redelivery delay` (labels approximate; exponential backoff may only be exposed via `More Configurations by Code`), `Retry attempted log level`, `Async delayed redelivery`, `Use Original Message`, `Log stack trace` | An unconnected cErrorHandler applies to all routes in the Route; connected applies to that sub-route. Camel default redelivery when none set: 0 redeliveries (route fails on first exception) |
| cOnException | `onException(A.class, B.class).maximumRedeliveries(n).redeliveryDelay(ms).handled(true|false).continued(true).useOriginalMessage().to(...)` | Catch specific exception types for the whole Route and run the connected sub-flow | `Exceptions` table (fully-qualified class names), `Set a redelivering tries count` + `Maximum redelivering tries`, `Redelivery delay`, `Non-blocking asynchronous behavior` (asyncDelayedRedelivery), `Exception behavior`: `Handle` (handled(true): exchange completes, caller gets current body), `Ignore` (continued(true): resumes route after failing step), `None` (rethrow after sub-flow), `Use Original Message` | Must be a start component (unconnected input). Exception object: `${exception.message}`, `${exception.stacktrace}`, `exchange.getProperty(Exchange.EXCEPTION_CAUGHT, Exception.class)` |
| cTry / cCatch / cFinally | `.doTry()...doCatch(X.class)...doFinally()...end()` | Scoped try/catch inside a route | cTry has output links `try`, `catch`, `finally`; cCatch: `Exceptions` list | Inside doTry the route error handler is bypassed |
| cIntercept | `intercept()`, `interceptFrom(uri)`, `interceptSendToEndpoint(uri).skipSendToOriginalEndpoint()` | Intercept every step / incoming / outgoing to endpoint | `Type`, `Endpoint URI`, `Skip send to original endpoint`; link `when` predicate | Start component with sub-flow |

## Route runtime semantics

Exchange model:
- `Exchange` = `in` message (body, headers), exchange properties, pattern
  (`InOnly`/`InOut`), exception. Camel 3+: `exchange.getMessage()`; `getOut()`
  is deprecated (and creating an Out message drops In headers unless copied).
- Headers travel with the message to transports (HTTP/JMS map them); exchange
  properties stay inside the route and are visible to error handlers and
  aggregation strategies (`CamelSplitIndex`, `CamelAggregatedSize`,
  `CamelFileName` is a header though).
- Body types by source: cFile -> `GenericFile<File>`; cFtp -> `GenericFile`
  with `RemoteFile`; cCXF PAYLOAD -> `CxfPayload`, POJO -> JAXB objects, RAW ->
  `InputStream`; cREST -> `String`/`InputStream` (`Streaming`) or JAXB/JSON
  bean if configured; cTalendJob output -> whatever tRouteOutput emits
  (`Document` or `String`); cJMS -> String/byte[]/Map/Object per JMS type.
  Convert early with cConvertBodyTo.
- Stream caching: `camelContext.setStreamCaching(true)` via cConfig/cJavaDSL
  (`.streamCaching()`) when a stream body is read more than once (wiretap,
  multicast, logging body then processing).

Simple language (Camel 3/4):

```
${body}                        ${bodyAs(String)}           ${mandatoryBodyAs(String)}
${header.CamelFileName}        ${headers.X}  (Camel 3+)    ${headerAs(X,int)}
${in.header.X} / ${out.header.X}   deprecated in Camel 3, REMOVED in Camel 4 -> ${header.X}
${exchangeProperty.X}          ${property.X} deprecated (Camel 2.15), removed in Camel 3
${exchangeId} ${routeId} ${camelId} ${threadName} ${hostname} ${messageTimestamp}
${exception.message} ${exception.stacktrace} ${exception.class}
${bean:myBeanId.method} / ${bean:myBeanId?method=m(${body},${header.X})}
${date:now:yyyyMMdd-HHmmss}    ${date:header.X:yyyy}      ${file:name} ${file:name.noext} ${file:parent}
${sys.user.home} ${sysenv.PATH} ${env:PATH} ${random(1,100)} ${type:org.apache.camel.Exchange.FILE_NAME}
${jsonpath($.customer.id)} (Camel 3.x+, needs camel-jsonpath)   ${xpath(/a/b)} (camel-xpath)
operators: == != > >= < <= contains !contains ~~ (case-insens) regex in range startsWith endsWith is null
logical: && ||  ; e.g. ${header.type} == 'gold' && ${body} contains 'VIP'
```

Quoting: the Studio field is a Java String, so `"${header.type} == 'gold'"`;
inner Simple string literals use single quotes; to compare with a Java
variable concatenate: `"${header.id} == '" + context.vip + "'"`.

Other languages in cMessageRouter/cSetBody: `xpath` (`/order/@type = 'A'`,
`xpath("...", String.class)` to get text), `jsonpath` (`$.store.book[?(@.price
< 10)]`), `groovy` (`request.body.contains('x')`, Camel 3: `body`, `headers`
map), `header` (header name), `constant`, `el`, `mvel`, `ognl`, `spel`
(`#{request.body}`), `sql` (`select * from table where field > 10` over
`java.util.List<Map>`), `xquery`, `bean` (bean method returning boolean).

cTalendJob data exchange:
- In the Job: `tRouteInput` (start; schema has a `body` column; reading
  headers requires Propagate Header which maps header names to context
  variables of the same name, values `toString()`'d), `tRouteOutput` (sets the
  exchange body from its `body` column; optional headers via schema? unverified),
  `tRouteFault` (returns body as fault -> exception in the route).
- A Job without tRouteInput/Output runs blind; return values are not propagated.
- Context params table passes Java expressions evaluated per exchange
  (`exchange.getIn().getHeader("id", String.class)` works in the value column).
- No documented Talend-specific header set by cTalendJob (an alleged
  `CamelTalendJobInput` header is unverified; do not rely on it).

Route context parameters: `Contexts` tab on the Route (same mechanism as
Jobs). Reference as `context.name` in any Java field; Camel property
placeholders `{{name}}` inside URIs resolve against the route's context as well
(Talend registers context variables with the Camel `PropertiesComponent`;
unverified for 8.0 R20xx). Override at runtime: OSGi -> `etc/<RouteName>.cfg`;
Microservice -> `--context=Prod --context_param name=value` or
`application.properties`.

Route versioning: Route `Version` (major.minor) in Properties; `Build Route`
and `Publish` embed it in the artifact version; Runtime can host several
versions side-by-side only if endpoint addresses differ (same `/services/x`
path = CXF "address already in use" style failure, see Gotchas).

Logging and metrics: `cLog` / `log:` endpoint -> `data/log/tesb.log`
(`etc/org.ops4j.pax.logging.cfg`, log4j2); SAM events for cCXF/cREST/
cTalendJob-wrapped services; JMX `org.apache.camel` MBeans (ExchangesCompleted,
MeanProcessingTime per route) via Jolokia/JConsole; microservice:
`/actuator/metrics` (+ Prometheus registry if enabled; unverified).

## Data Services (SOAP)

Service designer flow (Studio):
1. Repository > `Services` > `Create Service`: name, then either `Import WSDL`
   (file/URL; imports with external XSD imports must be resolvable, or use a
   single-file WSDL) or `Create new WSDL` (wizard generates a default
   document/literal WSDL with one operation `<ServiceName>Operation`, one port
   `<ServiceName>Port`, binding `<ServiceName>SOAP`, address
   `http://localhost:8088/services/<ServiceName>` (default port 8088 in
   Studio; unverified)).
2. Expand Service > port > operation; right-click operation > `Assign Job`
   (existing) or `Create New Job`: Studio generates a Job containing
   `tESBProviderRequest` (start) and `tESBProviderResponse`, and offers
   `tESBProviderFault` from the ESB > SOAP palette family. The Job is bound to
   the operation (shown in the Service tree; Job properties show `Service`).
3. `tESBProviderRequest`: schema fixed to one column `payload` of type
   `Document` (request body element). `Keep listening` (Studio runs: Job stays
   up handling requests until stopped; `Timeout` otherwise). In Runtime the
   provider is always listening (OSGi service).
4. Map with `tXMLMap` (Document in -> Document out; the output root element
   must match the WSDL response element and namespace). `tESBProviderResponse`
   schema: `payload` Document. `tESBProviderFault`: `payload` Document plus
   `Fault title`/message settings (unverified labels) -> SOAP Fault.
5. Right-click Service > `ESB Runtime Options` (per operation/port):

| Option | Effect | Needs |
|---|---|---|
| Use Service Locator | Provider registers endpoint in ZooKeeper at start, unregisters at stop; `Custom Properties` table (name/value) published for consumer filtering | `tesb-locator-client`, ZooKeeper reachable |
| Use Service Activity Monitor | REQ/RESP/FAULT events to SAM server | `tesb-sam-agent`, SAM server URL in `org.talend.esb.sam.agent.cfg` |
| Use Service Registry | Dynamic policy/endpoint lookup (enterprise, legacy) | Service Registry install; disables SAM and Business Correlation checkboxes |
| Use Authentication | `Username Token` (WS-Security UsernameToken, validated by Karaf JAAS / IAM), `SAML Token` (STS-issued, signed), `HTTP Basic`, `HTTP Digest` | STS for SAML; JAAS users for UT/Basic |
| Use Authorization | Role check per operation (IAM/Syncope roles) | IAM |
| Use Business Correlation | Correlation ID propagated/generated, stored in SAM | SAM optional |
| Log messages | Log request/response payloads via CXF logging interceptors | log level INFO in `org.apache.cxf.services` |

6. Run in Studio (Job runs, listens on WSDL address; WSDL at `?wsdl`), test
   with SoapUI/API Tester; build via `Build Job` > `OSGi Bundle For ESB` (or
   `Microservice`) or right-click Service > `Build Service` / `Publish`.

Runtime endpoint: `http://host:8040/services/<ServiceName>` (`?wsdl` for the
contract). The address in the WSDL is replaced by the relative CXF address
when deployed in Runtime (hostname/port dropped), so leave the WSDL default.

`tESBConsumer` (call a SOAP service from any Job):

| Setting | Notes |
|---|---|
| `Service configuration` | `...` button: WSDL URL/file -> pick `Service`, `Port`, `Operation` (populates request/response/fault schemas as `payload` Document) |
| `Endpoint` / `Address` | Overrides WSDL address; disabled when `Use Service Locator` (address becomes `locator://<ServiceName>`) |
| `Use Service Locator` + `Custom Properties` | Resolve provider via ZooKeeper; property filter must match provider's published properties |
| `Use Service Activity Monitor` | Consumer-side SAM events |
| `Use Service Registry` | Enterprise; hides SL, disables SAM/correlation |
| `Use Authentication` | `Username/Password` (UsernameToken), `SAML Token` (fields: STS endpoint/alias, or `Propagate credentials` from provider), `HTTP Basic`, `HTTP Digest`; `Use Service Registry` adds policy-driven variants |
| `Use Business Correlation` | Sends/propagates correlation ID header |
| `Die on error` | Unchecked -> use `Fault` output flow (`faultString`/payload) instead of killing the Job |
| Advanced | `Connection timeout(ms)`, `Receive timeout(ms)` (CXF `http.connection.timeout`/`http.receive.timeout`; default 30000/60000, unverified), `Use GZip compression` (unverified), `Enable MTOM`, `Log messages`, `Proxy host/port/user/password`, `Use SSL` keystore settings (or JVM `-Djavax.net.ssl.trustStore`) |
| Outputs | `Response` (payload Document), `Fault` (payload + fault string), plus `tESBConsumer_1_ERROR_MESSAGE` globalMap |

Build the request `payload` Document with `tXMLMap` (tmap-expressions.md),
`tFileInputXML` with a `Document`-typed column, or `tJavaRow` using dom4j
(`routines.system.Document d = new routines.system.Document();
d.setDocument(org.dom4j.DocumentHelper.parseText(xml));`).

WS-Security runtime config for provider Jobs in Runtime: STS/WSS properties
are read from `etc/org.talend.esb.job.service.cfg` (provider) and
`etc/org.talend.esb.job.client.sts.cfg` (consumer: `sts.wsdl.location`,
`sts.service.name`, `sts.endpoint.name`, `ws-security.username`,
`ws-security.signature.properties`...) - file names and keys from memory
(unverified).

## REST data services

`tRESTRequest` (start component; ESB > REST family):

| Setting | Notes |
|---|---|
| `REST Endpoint` | Studio: full URL, default `http://127.0.0.1:8088/` (or `http://localhost:8088/`, unverified exact default); Runtime: only the path (`/customers`), hostname/port dropped -> served at `http://host:8040/services/customers`; Microservice default port 8065; `0.0.0.0` to bind all interfaces |
| `REST API Mapping` table | one row per operation: `Output Flow` (name of the flow leaving tRESTRequest), `HTTP Verb` (GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS), `URI Pattern` (`/customers/{id}`, `/customers/{id}/orders`), `Consumes` (XML/JSON/FORM/MULTIPART/ANY, 7.x+ also `TEXT`), `Produces` (XML/JSON/ANY), `Streaming` (8.0; stream request body), `Comment` |
| Output flow schema | `body` column (type `Document` for XML/JSON converted to XML, or `String` for raw JSON/text) + one column per parameter. The schema `Comment` of a column selects the parameter kind: `path`, `query` (default when empty), `header`, `form`, `matrix`, `multipart`; column name = `{id}` placeholder / query/header name; nullable + default values supported |
| `Import API Definition` / `Export API Definition` | Load OAS 2.0 (Swagger), OAS 3.0 or RAML 1.0 (7.1+) from file/URL or from a Repository `REST API Definition` -> fills the mapping table and schemas; export generates OAS from the mapping |
| `Use Service Locator`, `Use Service Activity Monitor`, `Use Business Correlation`, `Log messages` | As for SOAP (SL registers REST endpoint by `Service name`) |
| `Use Authentication` | `Basic HTTP`, `HTTP Digest` (unverified), `OAuth2 Bearer`/`OpenID Connect` (token validation URL / JWKS; 7.x+, labels unverified), `SAML Token` |
| `Use Authorization` | Role mapping via IAM |
| Advanced: `Enable Cross Origin Resource Sharing (CORS)` | Adds `Access-Control-Allow-Origin/Methods/Headers/Max-Age` and answers preflight `OPTIONS`; fields `Allowed origins`, `Allowed methods`, `Allowed headers`, `Allow credentials`, `Max age` (unverified labels). Without it browser preflight fails with 405/no header |
| Advanced: `Convert JSON to XML`? / `Wrap JSON root`/`Drop JSON root`? | Controls the JSON<->Document conversion when `body` is Document (JSON arrays and root handling); exact labels unverified |
| Advanced: `Use multipart`, `Max message size`, `Attachment` settings | File upload endpoints |

Flow: `tRESTRequest` --(flow per operation)--> processing (`tXMLMap`,
`tExtractJSONFields`, `tDBInput` with `(String)globalMap.get("...")` from a
`tFlowToIterate`...) --> `tRESTResponse`. Each operation's flow must end in a
`tRESTResponse` (or a `tRESTResponse` reached via OnSubjobOk with the response
built in globalMap); exactly one response per request.

`tRESTResponse`:

| Setting | Notes |
|---|---|
| `Return Body Type` | `Document`, `String`, `Byte` (byte[]); input flow must have a single column named `body` of that type (Document -> serialized as XML, or JSON when the request `Produces` JSON) |
| `Return status code` | List: `OK (200)`, `Created (201)`, `Accepted (202)`, `No Content (204)`, `Bad Request (400)`, `Unauthorized (401)`, `Forbidden (403)`, `Resource Not Found (404)`, `Internal Server Error (500)`... or `Custom` numeric; drive dynamically with multiple tRESTResponse components behind a `tMap`/`Run if` or set via header |
| Advanced: `Response headers` | name/value pairs (e.g. `Location`, `Content-Type`) |
| Output | none; the component ends the flow. Output flow `body` exists on 7.2 for chaining (unverified) |

`tRESTClient` (consume REST; in 8.0 docs recommend `tHTTPClient` instead, see
connectors-catalog.md):

| Setting | Notes |
|---|---|
| `URL` + `Relative Path` | base + path; both Java expressions |
| `HTTP Method` | GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS |
| `Content Type` | shown for POST/PUT/PATCH: `XML`, `JSON`, `FORM`, `TEXT`? (body column from input flow; Document or String) |
| `Accept Type` | `XML`, `JSON`, `ANY` (ANY -> response kept as String; JSON with Accept JSON is converted into an XML Document when `Convert Response To DOM Document` is on) |
| `Query parameters`, `HTTP Headers`, `Form parameters` | tables (name/value Java expressions) |
| `Use Service Locator`, `Use Service Activity Monitor`, `Use Business Correlation` | as elsewhere |
| `Use Authentication` | `Basic HTTP`, `HTTP Digest`, `OAuth2 Bearer` (token string; some releases add client-credentials/password flows with `Token endpoint`, `Client id/secret`, `Scope`; unverified), `SAML Token` |
| `Die on error` | Off -> `Reject` flow with `errorCode`, `errorMessage` |
| Advanced | `Convert Response To DOM Document` (off -> response in `string` column), `Drop JSON request message root` / `Wrap JSON response root`? (unverified), `Connection timeout`, `Receive timeout`, `Use SSL` keystore, `Proxy`, `Log messages`, `Follow redirects`? |
| Output schemas | `Response`: `body` (Document) and/or `string` (String), `statusCode` (Integer, 7.x+); `Error`/`Reject`: `errorCode`, `errorMessage` |

Known behaviour: a 202/204 with empty body yields no row on the Response
flow in some versions (community reports), so branch on `statusCode` or use
tHTTPClient. Accept `JSON` converts the JSON to an XML Document (root element
`root`? unverified) - use `ANY` + `string` column + `tExtractJSONFields` for
raw JSON.

Status codes and errors: an uncaught exception in a tRESTRequest job returns
HTTP 500 with a generic body; to return 4xx/5xx deliberately route to a
`tRESTResponse` with the matching code. Request validation failures (bad
media type) are answered by CXF (415/406) before the flow runs.

## API Designer, API Tester, API Portal

| Tool | What | Key facts |
|---|---|---|
| Talend Cloud API Designer | Browser contract-first editor (OAS 3.0, OAS 2.0/Swagger, RAML 1.0): resources, operations, data types (JSON schema), examples, security schemes; `Try it`; hosted `Mock` service with example-based responses; export OAS/RAML; `Publish to API Portal`; share with Studio | Studio imports via `Metadata > REST API Definitions > Create` with source `Talend Cloud API Designer` (needs Cloud credentials/token in Studio preferences) or a downloaded file; drag the definition onto a Job -> `tRESTRequest` with mapping; onto a Route -> `cREST`. No one-click "Generate Job" from the Designer itself (unverified) |
| Talend API Tester | Chrome extension (Free edition) and Cloud app: requests, `Scenarios` (chained requests with `Assertions` on status/headers/body via JSONPath/XPath, and variable extraction), `Environments` with variables `${"var"}` syntax (unverified), import OAS/Postman, export project JSON | CI: `api-tester-maven-plugin` runs an exported scenario JSON from Maven (`mvn ... api-tester:execute`? exact goal/groupId unverified; requires Cloud account id/instance id and personal access token), producing JUnit-style reports |
| Talend API Portal | Static developer-portal generator (Hugo based) fed by API Designer publications; deploy on any web server; includes Try-it against mocks | Separate npm/Hugo project; version details unverified |
| Talend Cloud API Services (license) | Bundles Designer + Tester + Studio REST/Routes + Remote Engine | Routes/Data services appear as TMC artifact types |

## Microservices and Docker

Build: `Build Route` / `Build Job` > Build Type `Microservice (Spring Boot)` ->
`<Name>_<ver>.jar` (Spring Boot 2.x for Camel 3 builds; Spring Boot 3.x for
Camel 4 builds R2025-02+, Java 17). Also from Repository > Services (Data
Service microservice contains the Job + CXF endpoint).

```
java -jar CustomerRoute_0.1.jar                              # defaults: REST port 8065, context Default
java -jar CustomerRoute_0.1.jar --server.port=9090           # Spring Boot override
java -jar CustomerRoute_0.1.jar --context=Prod --context_param dbHost=db1 --context_param dbPort=5432
java -jar CustomerRoute_0.1.jar --spring.config.location=file:/opt/conf/application.properties
java -Xms256m -Xmx1g -Dlog4j2.configurationFile=/opt/conf/log4j2.xml -jar CustomerRoute_0.1.jar
```

`application.properties` keys that matter: `server.port` (REST/SOAP endpoint
port when the artifact exposes HTTP; cREST/tRESTRequest default 8065),
`server.servlet.context-path`, `server.ssl.key-store`, `server.ssl.key-store-password`,
`server.ssl.key-alias`, `management.endpoints.web.exposure.include=health,info,metrics,prometheus`,
`management.server.port`, `camel.springboot.*` (e.g. `camel.springboot.shutdown-timeout`),
`logging.level.*`. Actuator `/actuator/health` is on by default; Prometheus
scraping needs the micrometer registry on the classpath (Talend 7.2+ docs
mention Prometheus metrics for microservices; unverified).

Lifecycle: one CamelContext per jar; SIGTERM -> Camel graceful shutdown waits
for in-flight exchanges up to `shutdown-timeout` (default 45 s in Camel 3, 45 s
Camel 4). Memory: Spring Boot + Camel + Talend job classes idle ~300-500 MB;
size `-Xmx` to payload sizes (Document bodies are DOM = ~5-10x XML size).

Docker: Build type `Docker Image` uses a Maven docker plugin (fabric8 /
`docker-maven-plugin` in 7.x; Jib in 8.0, unverified) with options `Image
name`, `Image tag`, `Registry host`, `Push image`, `Base image` (Talend base
images or `eclipse-temurin`); requires a reachable Docker daemon
(`DOCKER_HOST`) unless Jib is used. Runtime args identical to the jar
(`docker run -p 8065:8065 -e ... image --context=Prod`). Kubernetes: expose
`/actuator/health` as readiness/liveness probe.

Talend Cloud Remote Engine runs published Routes/Data services as these
microservice jars inside the engine's JVM/process pool (there is no separate
"Remote Engine for Routes" product; the regular Remote Engine v2.x+ handles
them; unverified naming).

## Security

| Area | How | Config |
|---|---|---|
| Karaf console/JMX users | JAAS realm `karaf`, `etc/users.properties` (`user = password,role1,role2`; `tadmin = tadmin,admin,manager,viewer,systembundles,ssh,sl_admin,sl_maintain,sl_read,sam_user`? roles approximate), `etc/keys.properties` for SSH keys; encrypted passwords via `etc/org.apache.karaf.jaas.cfg` (`encryption.enabled=true`) | `jaas:*` commands; TAC uses these creds for ESB Conductor |
| HTTP Basic / UsernameToken for services | Validated against Karaf JAAS (`karaf` realm) or IAM/Syncope when configured; role check via `Use Authorization` | `etc/org.talend.esb.*.cfg`; Studio runs validate against Studio's own users list in Preferences > Talend > ESB (unverified) |
| SAML via STS | Consumer: `Use Authentication = SAML Token`, credentials to STS (UT or X.509) -> signed SAML assertion in WS-Security header; provider validates signature against STS cert in truststore | `etc/org.talend.esb.job.client.sts.cfg`, `etc/org.talend.esb.job.service.cfg`, keystores in `etc/keystores/` (names unverified) |
| OAuth2 / OIDC for REST | tRESTClient `OAuth2 Bearer`; tRESTRequest/cREST token validation (7.x+); or terminate OAuth at an API gateway in front of Runtime | component settings |
| HTTPS in Runtime | `etc/org.ops4j.pax.web.cfg`: `org.osgi.service.http.secure.enabled=true`, `org.osgi.service.http.port.secure=9001`, `org.ops4j.pax.web.ssl.keystore=etc/keystores/keystore.jks`, `org.ops4j.pax.web.ssl.password=`, `org.ops4j.pax.web.ssl.keypassword=`, `org.ops4j.pax.web.ssl.clientauthneeded=false`; optionally `org.osgi.service.http.enabled=false` to disable plain HTTP | Services then at `https://host:9001/services/...` |
| HTTPS in microservice | `server.ssl.*` Spring Boot keys | `application.properties` |
| Outbound TLS trust | JVM truststore (`-Djavax.net.ssl.trustStore` in `bin/setenv` / `etc/trun.*`? or `EXTRA_JAVA_OPTS`), or component `Use SSL` settings | |
| Karaf RBAC | `etc/jmx.acl.*.cfg`, `etc/org.apache.karaf.command.acl.*.cfg` restrict commands/MBeans per role | |
| IAM / Syncope | Users, groups, roles consumed by Authentication/Authorization; REST admin console | 7.x+, subscription only |
| Secrets in config | `etc/*.cfg` plain text; use Karaf `jasypt` encryption (`feature:install jasypt-encryption`) or OS-level permissions; Talend context passwords in Jobs are encrypted at design time only | |

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| cTalendJob runs but the Job sees null/default context values | Context params not passed: `Context Param` table empty, or `Propagate Header` off; headers only arrive as Strings | Fill the Context Param table with expressions (e.g. `exchange.getIn().getHeader("id",String.class)`), or enable `Propagate Header` and name headers exactly like the context variables; pass objects in the body |
| `Propagate Header` works in Studio but not after enabling `Fast Job Invocation` | Documented incompatibility of the two options for some Jobs | Disable `Fast Job Invocation` for that cTalendJob |
| Route bundle `Active` but `camel:route-list` empty / `NoSuchMethodError`, `ClassNotFoundException: org.apache.camel...` | Camel/CXF version mismatch: Route built with Studio R2025-02+ (Camel 4) deployed on a Camel 3 Runtime or vice versa; custom Bean compiled against another Camel API | Align Studio patch and Runtime patch (Camel 3 line ends at R2025-01); rebuild Routes after Runtime upgrade |
| Simple expression compiles but never matches (`when` always false) | Quoting: Java string vs Simple literal confusion, e.g. `"${header.type} == gold"` (unquoted literal) or `"${header.type} == \"gold\""` | Use single quotes inside: `"${header.type} == 'gold'"`; test with cLog `"type=${header.type}"` |
| `${in.header.X}` / `${property.X}` throw `Unknown function` | Removed syntax (Camel 3 removed `property.`, Camel 4 removed `in.header.`) | Use `${header.X}` and `${exchangeProperty.X}` |
| cMessageRouter: compile error "endChoice" or messages go to the wrong branch | Processing components placed directly after `when`/`otherwise`; or `when` order (first match wins) | Follow each `when`/`otherwise` with cDirect to a sub-route or tick `endChoice()`; order `when` links from specific to general |
| cSplitter with strategy returns only the last piece / original message | Aggregation strategy bean does not handle `oldExchange == null`, or `Use Strategy` not checked (Camel then continues with the original body) | Implement `aggregate(old,new)` returning `new` when `old == null`; check `Use Strategy` |
| cAggregate never completes / completes at 3 | Default `Number of messages` = 3; no timeout; correlation key differs per message | Set correlation expression (e.g. `constant` `true` for all), completion size/timeout/predicate; enable `Eager check` for predicate completion |
| tRESTRequest Job fails in Studio: `Address already in use` / `BindException` on 8088 | Another provider Job or earlier run still listening; two Jobs share the same endpoint port | Kill the previous run (Studio `Kill` on Run tab), change `REST Endpoint` port per Job; in Runtime use distinct paths since all share 8040 |
| REST service reachable on `localhost` only | `REST Endpoint` bound to `127.0.0.1`/`localhost` | Use `http://0.0.0.0:8088/` (Studio/standalone); in Runtime the path-only endpoint binds via Pax Web on all interfaces |
| Browser call fails with CORS error / preflight `OPTIONS` returns 405 | CORS not enabled on tRESTRequest/cREST | Advanced settings > `Enable Cross Origin Resource Sharing (CORS)`, set allowed origins/methods/headers; include `OPTIONS` if mapping manually |
| tRESTClient returns rows with empty `body` but non-empty `string` (or vice versa) | `Convert Response To DOM Document` toggles which column is populated; Accept `ANY` always yields String | Pick one: Document + Accept XML/JSON with conversion on, or String + `ANY` + conversion off; parse JSON downstream with tExtractJSONFields |
| tRESTResponse sends 200 with empty body | Input column not named `body`, or type mismatch with `Return Body Type` (String vs Document) | Rename the single input column to `body` and match the type |
| JSON with nested arrays arrives as Document with duplicated/wrapped elements, or arrays of one element lose the array | JSON->XML conversion (Jettison/CXF) has no native array notion | Receive as `String` (Consumes JSON, body String) and parse with tExtractJSONFields/JSONPath; or send `String` JSON built with tWriteJSONField in tRESTResponse |
| Deployed service returns 500 and log shows `ConnectionLoss`/`KeeperErrorCode` from ZooKeeper | `Use Service Locator` enabled but ZooKeeper not running or `locator.endpoints` wrong | `tesb:start-locator` or fix `etc/org.talend.esb.locator.cfg`; untick SL for environments without it |
| Consumer with `Use Service Locator` fails `No endpoint found for service {ns}Name` | Provider not registered (not started, different service QName/custom properties, SL session expired) | Check `zkCli` or SAM; ensure provider has SL enabled and the same service name; match Custom Properties |
| SAM-enabled service slow or errors `MonitoringService` unreachable; SAM server logs `Table EVENTS not found` | SAM agent URL wrong or SAM DB not initialised | Fix `service.url` in `org.talend.esb.sam.agent.cfg`; run the DDL for your DB (`add-ons/sam/db`) and point `org.talend.esb.datasource.*.cfg` at it; `tesb:start-sam` |
| `Import WSDL` fails: `Unable to resolve import` / `schema not found` | WSDL references relative XSD/WSDL imports not reachable from Studio (URL auth, relative paths) | Download the WSDL and all imports locally keeping relative paths, or flatten into one WSDL (SoapUI/wsdl flattening); check proxy settings |
| `feature:install` hangs or `Error resolving artifact ... mvn:` in an offline Runtime | Feature jars not in `system/`; `org.ops4j.pax.url.mvn.cfg` points to unreachable repos | Pre-populate `system/` (Talend provides offline feature packs), deploy KARs (self-contained), or set an internal Nexus mirror in `org.ops4j.pax.url.mvn.repositories` |
| Second Runtime on same host will not start: ports 8040/8101/1099/44444 in use | Default ports collide | Edit `etc/org.ops4j.pax.web.cfg`, `etc/org.apache.karaf.shell.cfg`, `etc/org.apache.karaf.management.cfg` before start; also `etc/system.properties` `karaf.name` |
| `tesb.log` fills with repeated `Installing bundle ... Failed to install` every second | Hot-deploy loop: broken artifact in `container/deploy` retried on each FileInstall poll | Remove the file from `deploy/`, fix (`bundle:diag`), redeploy; raise `felix.fileinstall.poll` |
| Bundle stays `Installed`/`Resolved`: `Unresolved requirement: Import-Package: com.foo` | OSGi: library used by Routines/Beans not exported by any bundle (embedded vs imported packages) | Add the jar as a Route/Job dependency so Studio embeds it (`Bundle-ClassPath`) or install it as a bundle (`bundle:install wrap:mvn:...`); check `bundle:diag <id>` |
| Microservice ignores `server.port` in `application.properties` | File not on the classpath/working dir, or overridden by `--server.port` arg / `SERVER_PORT` env | Pass `--spring.config.location=file:/path/application.properties`; remember env vars and CLI args win over the file |
| Provider Job in Studio with `Keep listening` grows memory and eventually OOMs | Never-ending job: per-request Document/DOM objects retained in globalMap or static collections; Studio run keeps statistics/trace on | Disable Statistics/Traces for long runs, avoid storing payloads in globalMap, test memory under load in Runtime instead of Studio, size `-Xmx` in `etc/trun`/`bin/setenv` |
| Same service deployed twice (new version) -> second one never activates or `Endpoint already registered` | Both bundles publish the same CXF address `/services/X` | Undeploy the old version first (TAC task `Update` does this), or use versioned paths (`/services/X/v2`) |
| cFile route re-processes the same files forever | `Noop` true without idempotent repo, or `Move`/`Delete` unset | Set `Move to` `.done` or `Delete`, or keep `noop=true` + `idempotent=true` (default with noop) and do not clear the in-memory repo by restarting |
| cJMS producer hangs ~20 s then `ExchangeTimedOutException` | InOut pattern waiting for a reply queue | Insert cSetExchangePattern `InOnly` before cJMS or set `disableReplyTo=true` |
| After Runtime upgrade, cHttp/cMQTT/cDirectVM routes fail to build | Camel component renames/removals (`http4`->`http`, `mqtt`->`paho`, `direct-vm`/`vm` removed in Camel 4) | Replace components per Camel migration guide; rebuild all Routes with the matching Studio |

## Sources

https://help.qlik.com/talend/en-US/components/8.0/mediation-route/ctalendjob
https://help.qlik.com/talend/en-US/mediation-components/8.0/mediation-route/ctalendjob
https://help.qlik.com/talend/en-US/mediation-components/7.2/mediation-route/ctalendjob-csetheader-ctimer-ctimer-configuring-how-message-is-processed
https://community.qlik.com/t5/Talend-Studio/Camel-to-Job-parameters/m-p/2363306
https://help.qlik.com/talend/fr-FR/mediation-components/7.3/mediation-apache-cxf/csoap-standard-properties
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2025-01/setting-runtime-options
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2025-11/setting-runtime-options
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/setting-runtime-options
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-06/using-rest-metadata-with-jobs-and-routes
https://help.qlik.com/talend/en-US/components/8.0/esb-rest/trestrequest
https://help.qlik.com/talend/en-US/components/7.3/esb-rest/trestrequest-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/esb-rest/trestclient
https://help.qlik.com/talend/en-US/components/7.2/esb-rest/trestclient-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/http/thttpclient
https://community.qlik.com/t5/Talend-Studio/The-REST-API-response-is-coming-in-weird-format/m-p/2539205
https://community.qlik.com/t5/Talend-Studio/TOS-TRestClient-call-doesn-t-return-anything-when-HTTP-202-and/m-p/2207759/highlight/true
https://help.qlik.com/talend/en-US/components/8.0/esb-rest/trestresponse
https://help.qlik.com/talend/en-US/components/7.2/esb-rest/trestresponse-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/esb-rest/trestrequest-trestclient-tlogrow-configuring-trestresponse-component-standard-component-esb-connect
https://community.qlik.com/t5/Talend-Studio/tRESTResponse-not-responding-JSON-body/m-p/2289613
https://help.qlik.com/talend/en-US/components/7.2/esb-soap/tesbconsumer-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/esb-soap/tesbconsumer-standard-properties
https://help.qlik.com/talend/en-US/installation-guide-windows/7.2/cheatsheet--start-and-stop-commands-for-talend-server-modules
https://help.qlik.com/talend/en-US/installation-guide-linux/8.0/cheatsheet-start-and-stop-commands-for-talend-server-modules
https://help.qlik.com/talend/en-US/studio-getting-started-guide-esb/7.3/launching-talend-runtime-and-its-infrastructure-services
https://community.qlik.com/t5/Talend-Studio/resolved-Problem-deploying-services-on-Karaf-not-start/m-p/2308462/highlight/true
https://help.qlik.com/talend/en-US/esb-container-administration-guide/7.3/basic-configuration
https://help.qlik.com/talend/en-US/esb-container-administration-guide/8.0/default-configuration
https://help.qlik.com/talend/en-US/esb-container-administration-guide/8.0/configuring-context
https://community.qlik.com/t5/Talend-Studio/How-to-list-the-URL-s-of-all-services-deployed-in-Talend-ESB/td-p/2366077
https://help.qlik.com/talend/en-US/release-notes/8.0/r2025-01-talend-runtime
https://help.qlik.com/talend/en-US/release-notes/8.0/r2025-02-talend-runtime
https://help.qlik.com/talend/en-US/core-framework-updates-of-esb-801-r2023-08/8.0/impacts-of-core-framework-updates-of-esb-801-r2023-08
https://help.qlik.com/talend/en-US/release-notes/8.0/r2023-08-talend-runtime-new-features
https://help.qlik.com/talend/en-US/release-notes/8.0/esb-new-features
https://help.qlik.com/talend/en-US/components/8.0/mediation-filter/cmessagerouter
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-07/trigger-connections-for-route
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-05/when
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/otherwise
https://help.qlik.com/talend/en-US/components/8.0/mediation-splitter/csplitter
https://help.qlik.com/talend/en-US/mediation-components/7.2/mediation-splitter/csplitter-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/mediation-aggregate/caggregate
https://help.qlik.com/talend/en-US/mediation-components/7.3/mediation-aggregate/caggregate-standard-properties
https://help.qlik.com/talend/en-US/mediation-components/8.0/mediation-splitter/csplitter-cdirect-csetbody-ctimer-using-csplitter-to-split-message-and-aggregate-replies-from-sub-messages
https://help.qlik.com/talend/en-US/mediation-components/7.3/mediation-aggregate/caggregate-cprocessor-cfile-cfile-aggregating-three-messages-into-one
https://help.qlik.com/talend/en-US/components/8.0/mediation-logs-and-errors/cerrorhandler
https://help.qlik.com/talend/en-US/mediation-components/8.0/mediation-logs-and-errors/conexception
https://help.qlik.com/talend/fr-FR/mediation-components/7.3/mediation-logs-and-errors/cerrorhandler-standard-properties
https://help.qlik.com/talend/en-US/mediation-components/8.0/mediation-apache-cxf/crest
https://help.qlik.com/talend/en-US/mediation-components/7.3/mediation-apache-cxf/crest-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/mediation-apache-cxf/crest-clog-cbeanregister-ctimer-providing-and-consuming-rest-service-using-crest
https://community.qlik.com/t5/Talend-Studio/difference-between-cCXFRS-and-tRESTClient/m-p/2334015/highlight/true
https://help.qlik.com/talend/en-US/components/8.0/rest/trest
