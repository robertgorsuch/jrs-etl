# Talend versions, editions, licensing and lifecycle (orientation for any Talend install)

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Additional primary sources read in full for this file: the "Support Policy for
Talend Software and Cloud Services (v2021.03.24)" PDF and the "Talend Service
Description Guide" PDF dated January 16, 2024 (both on
talend-legal-doc.s3.amazonaws.com), the help.qlik.com "Talend products
lifecycle" page snippets, Qlik Community Java 17 notices, and Maven Central
metadata for `org.talend.sdk.component` (Component Kit). Snapshot date of this
file: 2026-10-18. Latest Studio monthly release seen: 8.0.1 R2026-09.

## Contents
- [How to identify what you are looking at](#how-to-identify-what-you-are-looking-at)
- [Company and product timeline](#company-and-product-timeline)
- [Major version history](#major-version-history)
- [Talend 8 monthly R-releases](#talend-8-monthly-r-releases)
- [Lifecycle and support policy](#lifecycle-and-support-policy)
- [Version and platform support matrix](#version-and-platform-support-matrix)
- [Editions: client-managed (on-premises) products](#editions-client-managed-on-premises-products)
- [Editions: Talend Cloud (legacy SaaS)](#editions-talend-cloud-legacy-saas)
- [Editions: Qlik Talend Cloud (2024-2026)](#editions-qlik-talend-cloud-2024-2026)
- [Open Studio vs subscription feature table](#open-studio-vs-subscription-feature-table)
- [Licensing mechanics](#licensing-mechanics)
- [Support tiers](#support-tiers)
- [Upgrade and migration deltas](#upgrade-and-migration-deltas)
- [Documentation and community map](#documentation-and-community-map)
- [Qlik-era specifics](#qlik-era-specifics)
- [Gotchas](#gotchas)
- [Sources](#sources)

## How to identify what you are looking at

| Where | What to look at | What it tells you |
|---|---|---|
| Studio | `Help > About Talend Studio` | Edition name (e.g. "Talend Data Fabric", "Talend Open Studio for Data Integration", "Talend Cloud Data Integration"), base version `8.0.1`, build id, and in 8.0 the installed monthly release label (`R2024-05`). Also `Help > About > Installation Details` for installed features/patches (unverified exact label) |
| Studio folder | `plugins/org.talend.*_8.0.1.2021xxxx_xxxx/` names; `Talend-Studio-win-x86_64.ini` / `Talend-Studio-linux-gtk-x86_64.ini` / `Talend-Studio-macosx-cocoa.ini` (`-vm` path, `-Xmx`); `configuration/config.ini` (Eclipse/Talend build properties, `talend.studio.version`-style keys are (unverified)); `configuration/.settings`; `patches/` or `updates/` folder containing `Patch_2024xxxx_R2024-05_v1-8.0.1` style zips (unverified folder name) | Base build date, monthly release applied, JVM used |
| Studio license dialog | First start: "Enter license" / "Connect to Talend Cloud" / "Connect to TAC" | Client-managed (license text file) vs Cloud (login) vs Open Studio (no license step) |
| Workspace | `<workspace>/<PROJECT>/talend.project` contains `productVersion` (e.g. `8.0.1.20211109_1610-patch`) and `itemsRelationVersion`; each `.properties` item has `version` | Which Studio last saved the project; import into a lower version is refused |
| Exported/built job | `jobInfo.properties` in the zip root: `job`, `jobId`, `jobVersion`, `contextName`, `product_version`, `commandline_version` (unverified exact keys beyond `product_version`), `date` | Studio/CommandLine build that produced the job; log4j version by presence of `log4j2.xml` vs `log4j.xml` |
| TAC | Login page footer and `Help > About` (version + build), `Configuration` tab license block; `Licenses` page shows token, expiry, user counts | TAC version must match Studio monthly patch level (see Gotchas) |
| TMC (Talend Cloud / Qlik Talend Cloud) | `Processing > Engines` list shows each Remote Engine version (e.g. `2.14.x`) and Remote Engine Gen2 `R2026-03`; TMC itself is versionless SaaS | Engine upgrade needs |
| Remote Engine | `<re>/etc/version` style file (unverified), Karaf `shell:info` / `version` in the engine console, or TMC Engines page | Gen1 (Studio jobs/routes) vs Gen2 (Pipeline Designer/datasets) |
| Talend Runtime (ESB) | Karaf console `shell:info`, `system:version`, `<runtime>/version.txt` (unverified) | Karaf/CXF/Camel levels; see esb-routes-services.md |
| Generated pom | `pom.xml` of a built job: `<talend.studio.version>`-style properties and dependency versions (unverified exact names) | Which Studio generated the code |

Rule of thumb: a Studio that says `8.0.1` is NOT one version; the monthly
release label (R2022-01 ... R2026-09) is the real version. Always quote both.

## Company and product timeline

| Date | Event | Evidence |
|---|---|---|
| Aug-Sep 2005 | Talend founded in France (RCS registration 19 Sep 2005; first beta of Talend Open Studio shown Aug 2005; founders Bertrand Diard and Fabrice Bonan) | snippets (fr.wikipedia, Bloor, Computerworld) |
| Oct 2006 | Talend Open Studio (TOS) 1.0 first GA release. Early TOS generated Perl; Java code generation came with the 2.x line (2007) and Java became the default; Perl generation was dropped in later 4.x/5.x (unverified exact drop version) | snippets confirm Oct 2006; Perl/Java detail from memory |
| 2007-2009 | TOS 2.x, 3.x (Eclipse 3.x RCP). Talend Integration Suite (commercial, shared repository + "Talend Administration Center", originally "Talend Activity Monitoring Console" bundled) | memory (unverified) |
| 2010 | TOS 4.x; Talend MDM (Community Edition / Enterprise Edition) and Talend Data Quality lines; Talend acquired Sopera (Germany, ESB, Nov 2010) which became Talend ESB | guru99 snippet for MDM 2010; Sopera from memory (unverified) |
| 2011-2014 | 5.x line: 5.0 (late 2011), 5.1, 5.2 (2012), 5.3, 5.4 (2013), 5.5, 5.6 (late 2014). Talend Enterprise -> "Talend Platform for ..." naming; Big Data edition (Hadoop MapReduce, Pig) from 5.x | guru99 snippet for 5 in 2011; rest from memory (unverified exact months) |
| 2015 | 6.0 (summer 2015): Java 8 required, Spark batch jobs, new TAC; Talend Integration Cloud launched (iPaaS, first SaaS offering) (unverified exact month) | memory |
| 2016 | Nasdaq IPO (ticker TLND), July 2016; 6.2, 6.3 (6.3 added Spark 2 / Hadoop updates) | snippet confirms 2016 IPO |
| 2017 | 6.4, 6.5; Talend Integration Cloud rebranded "Talend Cloud" (around the 2017 summer release; "Talend Cloud" naming firmly in place by 2018) (unverified); acquired Restlet (API design/test, Nov 2017) -> Talend Cloud API Designer / API Tester (unverified date) | memory |
| 2018 | 7.0 (approx May 2018), 7.1 (approx Nov 2018); acquired Stitch (Stitch Data, Philadelphia, Nov 2018) -> Stitch plans still sold alongside Talend Cloud | memory; Stitch presence confirmed by Service Description Guide |
| 2019 | 7.2 (June 2019, confirmed); Talend Cloud Pipeline Designer GA (spring 2019) (unverified); acquired Gamma Soft (France, log-based CDC) -> "Talend Change Data Capture" product (2019) (unverified date; product confirmed in SDG) | lifecycle page; SDG |
| Feb 2020 | 7.3 (confirmed Feb 2020). Long-lived line, patched monthly as `7.3.1 R20xx-xx` | lifecycle page |
| Mar 2021 | Thoma Bravo agrees to take Talend private, approx USD 2.4 billion, USD 66/share; tender offer; completed around Aug 2021 | SEC filings, Financier Worldwide, Houthoff snippets |
| Nov 2021 | Talend 8 (8.0.1) GA for subscription customers (lifecycle page: "Talend 8 - November 2021") | lifecycle page |
| Jan 2022 | First Talend 8 monthly release R2022-01 (`Patch_20220121_R2022-01_v1-8.0.1`, released 2022-01-21). Talend Open Studio 8.0.1 published (last open-source release) | update.talend.com snippet; TOS 8.0.1 date from memory |
| Jan 2023 | Qlik announces agreement to acquire Talend (both Thoma Bravo portfolio companies) | TechTarget snippet |
| 16 May 2023 | Qlik closes acquisition of Talend | Qlik press release, GlobeNewswire |
| Nov 2023 | Talend blog "Update on the future of Talend Open Studio": open-source product to be discontinued effective 31 Jan 2024 | LinkedIn repost snippet |
| 31 Jan 2024 | Talend Open Studio discontinued. Qlik page: the open-source version "was retired and is no longer hosted or updated by Qlik and Talend", citing diminishing community adoption and lack of contribution | qlik.com page snippet |
| 2024 | Qlik Talend Cloud launched (Talend services hosted inside Qlik Cloud tenants; announced around Qlik Connect, June 2024) (unverified month) | memory |
| 30 Nov 2024 | Talend 7.3 end of life | lifecycle page, Qlik FAQ |
| 2025-2026 | Studio 8 continues monthly (R2025-01 ... R2026-09). Java 21 support added R2025-09, required R2026-06. Qlik Talend Cloud Migration Toolkit documented in 8.0 release notes (R2026-06 entry) | help.qlik.com snippets |
| Dec 2026 | End of purchasable Limited Extended Support for 7.3 | lifecycle page |

Naming summary: "Talend Open Studio" (free) -> "Talend Integration Suite" ->
"Talend Enterprise Data Integration" -> "Talend Platform for Data Management"
(5.x) -> "Talend Data Management Platform" (6.x+) -> "Talend Data Fabric"
(top bundle since 6.0, 2015). Under Qlik the portfolio is marketed as "Qlik
Talend Data Integration and Quality"; Studio remains documented as "Talend
Studio" (occasionally "Qlik Talend Studio" in marketing; help pages still say
Talend Studio) (unverified branding consistency).

## Major version history

Dates verified by snippet are marked; others are approximate (from memory).

| Version | GA | Retired | End of life | Headline changes |
|---|---|---|---|---|
| 5.6.x | Nov 2014 (approx) | 2017 (approx) | EOL (all pre-7.2 are EOL per lifecycle page) | Last 5.x; Java 7; Eclipse 3.x RCP; last release before component architecture refresh |
| 6.0 | mid 2015 (approx) | | EOL | Java 8 mandatory; Spark batch jobs (Big Data); new TAC UI; Talend Data Fabric bundle name; Eclipse 4.x RCP (unverified exact Eclipse) |
| 6.1 | late 2015 | | EOL | Spark Streaming; Data Preparation 1.0 |
| 6.2 | mid 2016 | | EOL | Data Stewardship; Cloud publishing |
| 6.3 | late 2016 | | EOL | Spark 2.x; Maven-based job build introduced in Studio (unverified: some place this at 6.3, others 7.0) |
| 6.4 / 6.5 | 2017 | | EOL | Git improvements; Data Catalog precursor (Metadata Manager); CI Builder maturing |
| 7.0 | approx May 2018 | | EOL | Studio Maven/Nexus 3; TCK ("Talend Component Kit") components start appearing; Spark 2 distributions; MapReduce deprecated; Pig/Storm deprecated (unverified) |
| 7.1 | approx Nov 2018 | | EOL | Dynamic distributions for Hadoop (unverified); Data Catalog 7.1 |
| 7.2 | Jun 2019 (verified) | Jan 2021 (verified) | Jun 2022 (verified) | Databricks; Remote Engine Gen2 groundwork |
| 7.3 | Feb 2020 (verified) | May 2023 (verified) | 30 Nov 2024 (verified); paid Limited Extended Support through Dec 2026 (verified) | Monthly patches `7.3.1 R2020-xx ... R2023-xx`; log4j2 option for jobs (R2021-xx, unverified); OpenJDK 11 added for Runtime/ESB (recommended 11.0.6+, verified for ESB runtime); Java 8 remains Studio baseline |
| 8.0 (8.0.1) | Nov 2021 (verified) | not announced | not announced | Java 11 baseline; Git only (SVN removed) (unverified); Eclipse 4.x 2020-era base (unverified); log4j2 only; Feature Manager / update-site installs; Spark Universal; monthly R-releases; Java 17 from R2023-10, mandatory R2024-05; Java 21 from R2025-09, mandatory R2026-06 |

Talend Data Catalog has its own lifecycle: TDC 7.3 GA Jan 2020, retired Apr
2022, EOL Dec 2022; TDC 8.0 GA Mar 2022, EOL 31 Dec 2024 (community banner);
TDC 8.1 current (verified snippets). Talend MDM has an End-of-Life notice page
in both the 7.3 and 8.0 release notes (help.qlik.com `.../release-notes/8.0/mdm-end-of-life`);
MDM is no longer part of new sales (exact EOL date not captured; see
data-quality-governance.md).

## Talend 8 monthly R-releases

Mechanics (verified by patch-note URLs and naming):
- One cumulative "monthly release" per month, labelled `R<year>-<month>`;
  package name `Patch_<yyyymmdd>_R<yyyy>-<mm>_v1-8.0.1`. Re-spins get a `v2`
  suffix (`R2022-03v2`, `R2024-11v2`, `R2025-01v2`, `R2025-09v2`).
- Full installers are periodically re-cut with a monthly release baked in,
  e.g. "Full Installer Release 8.0.1-R2022-10-RT".
- Patch notes live at
  `https://update.talend.com/Studio/8/updates/<R-label>/PATCH_RELEASE_NOTE.html`
  (`.../updates/latest/...` = current; R2026-09 at snapshot time) and at
  `https://help.qlik.com/talend/en-US/patch-notes/8.0/<r-label>`.
- Each note lists new features by product line code (TDI, TDQ, APPINT = ESB,
  TBD, TCK connectors) plus a "CVE fixes" section (R2022-01: xercesImpl and
  log4j-related updates).
- Studio applies them via `Help > Check for updates` / Feature Manager
  (online, from update.talend.com or a TAC/Nexus-hosted mirror) or manually
  via the TAC "Software update" repository. TAC, CommandLine, JobServer and
  Talend Runtime have matching monthly patches and must be kept at the same
  level as Studio (see Gotchas).

Notable monthly changes (verified items marked; others from memory, unverified):

| R-release | Change |
|---|---|
| R2022-01 | First monthly; Avro in tKafka components, Azure Blob API updates; log4j CVE fixes (verified) |
| R2022-02 | Remote Engine Gen2 switches to monthly `R2022-02` labelling (verified in lifecycle table) |
| R2022-05 | TMC release notes archive entry (verified URL only) |
| R2022-xx | Progressive replacement of javajet connectors by TCK connectors (Salesforce, NetSuite, Workday, Marketo, Azure, Google ...) (unverified timing) |
| R2023-xx | Snowflake key-pair authentication; Databricks newer runtimes; Spark Universal 3.3 (unverified) |
| R2023-08 | Spark Universal fixes referenced in patch notes (verified URL) |
| R2023-10 | Java 17 support introduced for Studio; project setting for Java 17 compatibility must be enabled when switching (verified) |
| R2023-11 | RHEL 9 and Rocky Linux 9 supported from this patch (verified) |
| R2023-12 | Fix "Unable to set Yarn Resources Allocation to Dynamic in Universal Distribution" (verified) |
| R2024-01 | macOS Sonoma supported from this patch (verified) |
| R2024-05 | Java 17 mandatory to run Studio and most Talend modules; artifacts may still target Java 8/11 at execution (verified) |
| R2024-05 | Spark Universal Local RDD runtime exception fixed (verified) |
| 2024-2025 | Studio login to Qlik Talend Cloud (Qlik account), publish artifacts to Qlik Talend Cloud tenants; Spark Universal 3.4/3.5; Databricks 13.x/14.x/15.x LTS (unverified) |
| R2025-01 | Studio User Guide version "8.0-R2025-01" documents Dynamic distributions as deprecated; "Migrate Distribution to..." action (verified) |
| R2025-06 | macOS Sequoia supported from this patch (verified) |
| R2025-09 | Java 21 supported for Studio (verified) |
| R2026-03 | Remote Engine Gen2 current label at snapshot (verified) |
| R2026-06 | Java 21 required for Studio; RHEL 8.6 double-click launch no longer works (command-line launch workaround) (verified); Qlik Talend Cloud Migration Toolkit release-notes entry (verified URL) |
| R2026-09 | Latest at snapshot (`updates/latest`) (verified) |

Component Kit (TCK, `org.talend.sdk.component`) versions as a proxy for the
runtime stack (Maven Central dates, verified):

| TCK version | Date | Stack |
|---|---|---|
| 1.1.0 | Sep 2018 | Beam 2.7.0, CXF 3.2.6 (7.0/7.1 era) |
| 1.1.10 | Jun 2019 | 7.2 era |
| 1.30.0 | Feb 2021 | Spark 2.4.7, Beam 2.27, CXF 3.4.1 (7.3 patches) |
| 1.40.0 | Dec 2021 | Spark 3.2.0, Beam 2.33 (8.0.1 GA) |
| 1.50.0 | Oct 2022 | Spark 3.2.0, CXF 3.5.2 |
| 1.60.0 | Aug 2023 | Spark 3.2.2, Beam 2.46, CXF 3.5.6 |
| 1.80.0 | Apr 2025 | Spark 3.2.2, CXF 3.5.10 |
| 1.90.0 | Mar 2026 | |
| 1.95.0 - 1.95.3 | Aug-Sep 2026 | |
| 1.2610.0 | Sep 2026 | New `1.YYMM.x` numbering; compiled for Java 17; Spark 3.5.7, Beam 2.46, CXF 3.6.12 |

## Lifecycle and support policy

Verified from the 2021 Support Policy PDF and the Jan 2024 Service Description
Guide (SDG):

- Release types: Major Release (X.y.z, "generally one per year" in 2021
  wording; by 2024 the policy defines only Major Release + Monthly Release +
  Patch). Monthly Releases carry features and fixes; Patches are cumulative
  bug-fix packages.
- Product Support Lifecycle: when a new Major Release becomes GA, the previous
  release is Retired 18 months after that date. When a Monthly Release
  (2021 text: Minor Release) becomes GA, the previous release within the same
  major is Retired 12 months later.
- GA: available for sale, fully supported in documented Supported
  Environments.
- Retired: not for general sale; no enhancements/monthly releases, only
  monthly Patches (bug fixes and certain CVE fixes) "for up to 18 months"; no
  new product keys except for existing customers, key duration not beyond EOL.
- End of Life: no sale, no support, no Monthly Releases or Patches; Talend
  does not guarantee third-party fixes; support possible "at an agreed upon
  fee". Lifecycle page: extended support may be purchased for an additional
  12 months after end of support; 7.3 Limited Extended Support runs through
  Dec 2026 (third-party blog says Severity 1 only, non-renewable; unverified).
- Binary compatibility: Talend "strives to preserve" compatibility across
  monthly releases but may drop third-party versions no longer supported by
  their publisher, documented in release notes.
- Cloud Service Client (Studio when used with Talend Cloud): only the GA
  client is guaranteed interoperable; prior releases are Retired, EOL after
  18 months (2021 text).
- Lifecycle table (SDG Jan 2024 + help.qlik.com page, verified):

| Product | Released | Retired | End of life |
|---|---|---|---|
| Talend 8 | Nov 2021 | -- | -- |
| Talend 7.3 | Feb 2020 | May 2023 | 30 Nov 2024 (+ paid extended to Dec 2026) |
| Talend 7.2 | Jun 2019 | Jan 2021 | Jun 2022 |
| Talend Data Catalog 7.3 | Jan 2020 | Apr 2022 | Dec 2022 |
| Talend Data Catalog 8 | Mar 2022 | -- | 8.0: 31 Dec 2024; 8.1 current |
| Remote Engine Gen1 2.10 | Feb 2021 | Feb 2022 | Aug 2022 |
| Remote Engine Gen1 2.11 | Nov 2021 | -- | -- (2.14 current in 2026; 2.13+ requires Java 17) |
| Remote Engine Gen2 | R2022-02 | monthly; only the most recent version is supported at any time | |

"All versions not listed in the table have already reached end of life"
(so 5.x, 6.x, 7.0, 7.1 are EOL).

## Version and platform support matrix

Studio / server platform support by major version. Verified cells are from
help.qlik.com "Compatible Java Environments" and "Compatible Operating
Systems" (8.0) snippets; the rest is model knowledge (unverified).

| Area | 5.6 | 6.x | 7.0-7.2 | 7.3 | 8.0 |
|---|---|---|---|---|---|
| Studio JDK | Java 7 (6 tolerated early) (unverified) | Java 8 (Oracle JDK, OpenJDK) | Java 8 (Oracle or OpenJDK/Zulu) | Java 8 for Studio; OpenJDK 11 added for Runtime/ESB and later Studio patches (11.0.6+ recommended, verified for ESB) | Java 11 (Zulu OpenJDK recommended) at GA; Java 17 from R2023-10, mandatory R2024-05; Java 21 from R2025-09, mandatory R2026-06 (verified). Oracle JDK no longer the documented default |
| Big Data job compile | n/a (MapReduce) | Java 8 | Java 8 | Java 8 | Java 8 only for distribution-specific Big Data jobs in early 8.0 (Zulu 11 unsupported, verified ~2023); Spark Universal with Java 11/17 later (unverified) |
| Eclipse RCP base | 3.6/3.7 (unverified) | 4.4-4.6 (unverified) | 4.6-4.7 (unverified) | 4.7-4.8 (unverified) | 4.x 2020-era (unverified) |
| Windows | 7/8/Server 2008-2012 | 7/8.1/10, Server 2012-2016 | 10, Server 2012-2019 | 10, Server 2012-2019 | 10, 11, Server 2012-2025 (verified) |
| Linux (Studio) | RHEL/CentOS 6, Ubuntu 12-14 | RHEL 6/7, Ubuntu 14/16 | RHEL 7, Ubuntu 16/18 | RHEL 7/8, Ubuntu 18/20 | RHEL 8 (8.6 double-click launch broken from R2026-06), RHEL 9 and Rocky 9 (R2023-11+) (verified); Ubuntu not listed in the 8.0 Studio OS page snippet (unverified status) |
| macOS (Studio) | 10.8-10.10 | 10.10-10.12 | 10.12-10.14 | 10.13-10.15 | Big Sur, Monterey, Ventura, Sonoma (R2024-01+), Sequoia (R2025-06+) (verified); Apple Silicon runs via x86_64 build under Rosetta; native arm64 build status (unverified) |
| Studio RAM | 2 GB min | 4 GB min | 4 GB min, 8 GB rec. | 4 GB min, 8 GB rec. | 8 GB rec., 16 GB for Big Data; `.ini` default roughly `-Xms512m -Xmx1536m` in 7.x and larger in 8 (unverified exact) |
| TAC database | H2 (default), MySQL, Oracle, MS SQL | + PostgreSQL, MariaDB | same | same | H2 (eval only), MySQL 8, MariaDB, PostgreSQL 12-16, Oracle 19c, MS SQL 2017-2022 (unverified exact) |
| TAC/AMC browsers | IE, Firefox, Chrome | IE11, Firefox, Chrome | IE11, Edge, Firefox, Chrome | Edge, Firefox, Chrome | Chromium Edge, Firefox, Chrome (IE dropped) (unverified) |
| SCM | SVN, Git (Git from 5.x) | SVN, Git | SVN, Git | SVN, Git | Git only (unverified but widely documented); GitHub, GitLab, Bitbucket, Azure DevOps, generic https/ssh |
| Artifact repo | n/a | Nexus 2 | Nexus 2 and 3, Artifactory | Nexus 2/3, Artifactory | Nexus 3, Artifactory (Nexus 2 dropped) (unverified) |
| Build | Studio export (Ant-like) | Maven arrives (6.3+) (unverified) | Maven + Nexus; CI Builder plugin | Maven; CI Builder `ci.builder` 7.3 | Maven 3.6+; CI Builder 8.0 (`-Dlicense.path`, `-Dupdatesite.path`) see deployment-runtime.md |
| Spark / Hadoop | MapReduce, Pig (TOS BD) | Spark 1.x-2.x, MapReduce, Storm; CDH/HDP/MapR/EMR | Spark 2.x; dynamic distributions (7.1+); MapReduce deprecated | Spark 2.4; Databricks; Dataproc; CDP | Spark Universal (2.4 ... 3.5); Databricks, EMR, Dataproc, Synapse, CDP, Kubernetes; built-in and dynamic distributions deprecated (verified). Details in big-data-spark.md |
| Talend Runtime (Karaf/CXF/Camel) | Karaf 2.x/CXF 2.7/Camel 2.1x | Karaf 4.0/CXF 3.1/Camel 2.17 (approx) | Karaf 4.1/CXF 3.2/Camel 2.21 (approx) | Karaf 4.2/CXF 3.3/Camel 2.24 (approx) | Karaf 4.3-4.4/CXF 3.5-3.6/Camel 3.x; Camel 4 move with Java 17 in later releases (unverified). See esb-routes-services.md |
| Admin console | TAC only | TAC; Talend Integration Cloud | TAC; Talend Cloud TMC | TAC; TMC | TAC (client-managed); TMC in Talend Cloud and in Qlik Talend Cloud |
| log4j for jobs | log4j 1.2 | log4j 1.2 | log4j 1.2 | log4j 1.2 default, log4j2 option (unverified) | log4j2 only (`log4j2.xml` in built jobs) |

## Editions: client-managed (on-premises) products

From the Jan 2024 Service Description Guide (verified names and inclusions).
"Entry-level Software": Talend Data Integration; Talend Big Data (includes
Data Integration); Talend ESB. "Platform Software": Talend Data Management
Platform (includes Data Integration); Talend Big Data Platform (includes Data
Management Platform); Talend Data Services Platform (includes Data
Management Platform); Talend Real-time Big Data Platform (includes Big Data
Platform and Data Services Platform); Talend Data Fabric (includes Real-time
Big Data Platform, Talend MDM Platform, and the Talend Cloud Data Fabric
cloud service). "Software Add-Ons": Cloud Flex Add-on, ESB Runtime, Data
Services Runtime, Data Preparation, Data Stewardship, Platform Admin Users,
Data Catalog. Separate product: Talend Change Data Capture (ex Gamma Soft;
Manager + source/target engines; licensed Per Source).

| Edition (abbrev.) | Adds on top of | Key Studio features (verified list) | Admin | License units |
|---|---|---|---|---|
| Talend Data Integration (TDI) | -- | Shared repository, continuous integration, audit, Job compare, impact analysis, test cases, debugging/tuning, metadata bridge, distant run, parallelization, dynamic schema, Joblets, reference projects, versioning, standalone export, CDC, automatic documentation, controlled patch management; connector families RDBMS/MQ/Cloud DB/Cloud storage/Technologies (incl. SCD, CDC, Avro, ORC, Parquet)/SaaS (incl. SAP ERP and BW, Salesforce, Workday, NetSuite, Marketo, ServiceNow)/Big Data file and Hive connectors/NoSQL/Security | TAC (users, projects, servers, Job Conductor, logs, AMC, MetaServlet API) | Named User, Concurrent User |
| Talend Big Data (TBD) | TDI | Native Spark batch code, Spark Job designer, Spark Universal incl. Kubernetes, dynamic distribution for Cloudera, dynamic schema in Spark, YARN scheduling, Knox/Kerberos; HDFS, HBase, Hive, Sqoop, Impala, Kudu components; Databricks, Delta Lake, Synapse Spark pools, EMR, HDInsight, CDP, Dataproc | TAC | Named, Concurrent |
| Talend ESB | -- | Routes, SOAP/REST services, WS-Policy security, EIPs, ActiveMQ backbone, Service Locator/Registry, XKMS, OSGi features; Talend Runtime | TAC (ESB Conductor) / TMC | Named, Concurrent, Per Core, Production Runtime, Non-Production Runtime; at least one Runtime mandatory |
| Talend Data Management Platform (TDMP, historically "Talend Platform for Data Management") | TDI | Continuous delivery, visual hierarchical mapping (Talend Data Mapper: XML, JSON, SAP IDoc, EDI), Repository Manager; Data Quality: profiling, masking/encryption, standardization, DQ data mart, semantic discovery, survivorship, matching/dedup, pattern library, Benford, column set/time correlation analyses; HA/load balancing/failover for tasks, engine clusters, SSO; 2 Named Users each of Data Preparation and Data Stewardship | TAC | Named, Concurrent; Admin User add-on |
| Talend Big Data Platform (TBDP) | TBD + TDMP | Spark MLlib components; DQ on Spark/Hadoop (cleansing, profiling, masking, parsing, matching), HDFS file profiling | TAC | Named, Concurrent |
| Talend Data Services Platform (TDSP) | TDMP | ESB capabilities + microservice build (Spring Boot), JMX/Jolokia, containerized services | TAC | Named, Concurrent, Per Core, Prod/Non-Prod Runtime |
| Talend Real-time Big Data Platform (TRTBDP) | TBDP + TDSP | Spark Streaming code; Kafka, Kinesis, Google PubSub | TAC | Named, Concurrent, Per Core, Runtimes |
| Talend Data Fabric (TDF) | TRTBDP + MDM Platform + Cloud Data Fabric | Everything, including MDM (now EOL) and the cloud entitlement | TAC + TMC | per contract |

Older names you will meet in 5.x/6.x installs: "Talend Enterprise Data
Integration", "Talend Platform for Data Management", "Talend Platform for Big
Data", "Talend Platform for Data Services", "Talend Platform for MDM",
"Talend Real-Time Big Data Platform", "Talend Open Studio for Data Quality
/ ESB / Big Data / MDM" (free lines; TOS for MDM and TOS for Data Quality
disappeared well before 8.0, approx 6.x/7.x) (unverified exact versions).

## Editions: Talend Cloud (legacy SaaS)

Talend Cloud = multi-region SaaS (regions `us`, `us-west`, `eu`, `ap`, `au`;
URLs like `https://<region>.cloud.talend.com`, TMC at
`https://tmc.<region>.cloud.talend.com`) (unverified exact hostnames). It
hosts Talend Management Console (TMC), Pipeline Designer, Data Preparation,
Data Stewardship, Data Inventory, API Designer/Tester, and Cloud Engines;
Studio is the "Cloud Service Client" you install locally. From the Jan 2024
SDG (verified):

| Cloud offering | Tier | Includes | Engine Tokens included |
|---|---|---|---|
| Stitch Advanced / Premium / Ultimate / Platform / Connect | Entry-level | Stitch replication (rows per month: 100M / 1B / 9B ...) | n/a |
| Talend Cloud Pipeline Designer Standard | Entry-level | Pipeline Designer, TMC, basic dataset inventory, 2 environments | 18,000 (Remote Engines only) + a design-only Cloud Engine |
| Talend Cloud Data Integration (TCDI) | Entry-level | Studio (same feature list as TDI) + Pipeline Designer + Data Preparation + Data Stewardship users; TMC with 31-day log retention, 2 environments, API automation, SSO | 45,000 |
| Talend Cloud Big Data | Entry-level | TCDI + Spark batch/Spark Universal | 45,000 |
| Talend Cloud Data Management Platform | Platform | TCDI + TDMP Studio features + DQ; HA/failover, engine clusters, static IPs, unlimited environments; 2 DP + 2 DS users | 90,000 |
| Talend Cloud Big Data Platform | Platform | + Spark MLlib, DQ on Spark | 90,000 |
| Talend Cloud API Services Platform | Platform | + Data Services/Routes, microservices, API Designer and Tester users | 90,000 |
| Talend Cloud Real-time Big Data Platform | Platform | Big Data Platform + API Services Platform + Spark Streaming | 90,000 |
| Talend Cloud Data Fabric | Platform | Everything above; add-ons Admin User, Concurrent Admin User, Cloud Flex, DP/DS/API users | 90,000 |
| Talend Cloud Data Fabric Capacity Bundle | Platform | Data Fabric + Data Inventory, licensed by Capacity Band: 200 Jobs (distinct artifact IDs/month), 20,000 Executions/month, 50,000 Duration minutes/month; overage billed monthly at 125% of annual unit price | included |
| Add-ons | | Data Preparation (10 Named Users), Data Stewardship (5), Data Inventory (5/10/25 base users), Data Catalog (Standard / Advanced / Advanced Plus; concurrent admin/producer and consumer users), API Designer and Tester (5), Engine Tokens (9,000 or 45,000 packs), Platform Admin User | |

Engine Tokens (verified): a Cloud Engine consumes 45,000 tokens; a Remote
Engine consumes 9,000 tokens; tokens can be mixed. Microservices generated
code may only run on a licensed Remote Engine.

## Editions: Qlik Talend Cloud (2024-2026)

- Qlik Talend Cloud (QTC) = Talend services delivered inside a Qlik Cloud
  tenant (`https://<tenant>.<region>.qlikcloud.com`), alongside Qlik Cloud
  Analytics and Qlik Cloud Data Integration (the Replicate-derived pipelines,
  Data Gateway - Data Movement). Studio artifacts, TMC, Remote Engines and
  Pipeline Designer are exposed from the Qlik Cloud hub ("Data Integration"
  area) (unverified layout detail).
- Account migration is mandatory: "To continue to access Talend Management
  Console, it is mandatory to migrate your Talend Cloud account to Qlik"
  (verified; help page "Migrating your account to Qlik for Talend Management
  Console access").
- Editions marketed as Qlik Talend Cloud Starter, Standard, Premium and
  Enterprise, with capacity-based pricing (Qlik Cloud "capacity" metrics such
  as data moved / compute) replacing Named User + Engine Token bundles for new
  deals (unverified; Qlik pricing pages were not reachable). Existing Talend
  Cloud contracts keep Named User / Engine Token metrics until renewal
  (unverified).
- Migration tooling (verified names): "Qlik Talend Cloud Migration Toolkit"
  (user guide at `help.qlik.com/talend/en-US/qlik-talend-cloud-migration-toolkit-user-guide/Cloud/...`)
  plans and performs migration of TAC assets to TMC: inventories and migrates
  users, groups, projects and authorizations; migrates tasks (arrive paused;
  resume to activate triggers); a recent release added Git push of upgraded
  code; TAC "start/restart from the middle of a plan" has no TMC equivalent.
  Hybrid guide page "Migrating Data from Talend Administration Center to
  Talend Management Console" (`hybrid-installation-guide-linux/Cloud/tac-to-tmc-migration`).
  Qlik "OP2C" (on-premises to cloud) FAQ on Qlik Community. Qlik Cloud side:
  `help.qlik.com/en-US/migration/...` pages ("Migrating the runtime assets",
  "Selecting the task artifact origin").
- TAC end-of-life: no dated sunset announcement found in snippets; TAC
  remains part of Talend 8 client-managed products and is patched monthly.
  Treat "TAC is being retired" claims as (unverified) and check the current
  lifecycle page.
- Studio under Qlik: monthly releases continue (R2024-xx, R2025-xx, R2026-09
  latest seen); no Studio end-of-support date announced in snippets
  (unverified absence). Studio now requires Java 21 (R2026-06+).

## Open Studio vs subscription feature table

TOS = Talend Open Studio for Data Integration / Big Data / ESB (Apache License
2.0 for Studio code, verified by Qlik Community and the 6.0 install guide;
some early TOS releases and community components were GPL (unverified)).
Final TOS release 8.0.1 (Jan 2022, no monthly updates); downloads ended
31 Jan 2024. "Subscription" = any TDI/TDMP/... or Cloud edition.

| Capability | Open Studio | Subscription | Notes |
|---|---|---|---|
| Local project, Job designer, tMap, routines, contexts | yes | yes | |
| Joblets | yes | yes | Available in TOS |
| "Store temp data" in tMap, ELT components, SCD components (tMysqlSCD, tOracleSCD ...) | yes | yes | SCD is in the open component set (unverified for every DB) |
| Multi-thread execution flag (Job settings) | yes | yes | Simple subjob parallel flag exists in TOS |
| tParallelize, Partitioner/Collector/Departitioner (row-level parallelization), "Parallel execution" on DB outputs | no | yes | SDG lists "parallelization" as subscription |
| Dynamic schema (`Dynamic` type) | no | yes | Subscription only |
| CDC (tMysqlCDC etc., CDC wizard) | no | yes | SDG lists CDC as subscription |
| Test cases (tCreateTestCase/ `Test Cases` node) | no | yes | |
| Shared/remote repository (Git/SVN), reference projects, branches, locking | no (local projects only) | yes | TOS cannot connect to TAC/TMC |
| TAC / TMC, Job Conductor, scheduling, AMC server | no | yes | TOS users schedule exported jobs with cron/Task Scheduler |
| Publish to Cloud / Qlik Talend Cloud | no | yes | |
| Audit, Job compare, impact analysis, metadata bridge (MIMB) | no | yes | |
| Automatic documentation (`Generate Doc as HTML`) | partial (basic HTML doc exists in TOS, unverified) | yes | SDG lists automatic documentation under subscription |
| Distant run (Studio -> JobServer) | no | yes | |
| Talend Data Mapper (tHMap, hierarchical mapping) | no | yes (TDMP+) | |
| Repository Manager | no | yes (TDMP+) | |
| Data Quality components (tMatchGroup, tStandardize*, tRule, tDataMasking, profiling perspective) | TOS for DQ had profiling only (discontinued); no DQ components in TOS DI | yes (TDMP+) | |
| Spark batch jobs | TOS for Big Data: yes (Spark batch, limited distributions) | yes | Spark Streaming subscription only (RTBDP) |
| MapReduce/Pig jobs | TOS BD <= 7.x | removed in 8 (unverified) | |
| ESB Routes and Data Services | TOS for ESB: yes (design + Talend Runtime) | yes | ESB Conductor/TMC deployment subscription only |
| SAP connectors (tSAP*), Mainframe (tFileInputEBCDIC via TDM), Microsoft CRM/AX, NetSuite, Workday, ServiceNow | mostly no | yes | SDG lists SAP ERP/BW etc. under subscription connector list |
| Salesforce, MongoDB, Snowflake, Redshift, BigQuery, Kafka basics | yes (many existed in TOS) | yes | Newer TCK versions subscription-only (unverified per connector) |
| Feature Manager / monthly updates | no (TOS 8.0.1 frozen) | yes | |
| Talend Exchange community components | yes (Exchange sunset; site unreliable) | yes | Exchange shut down in the Qlik era (unverified date) |
| CI Builder (Maven plugin) | no | yes | needs license + update site |
| License file / login | none | required | |

"Components availability by license" page on help.qlik.com is the
authoritative per-component matrix (search that phrase; URL not captured).

## Licensing mechanics

- Open Studio: no license file; Apache 2.0; `license.txt` style notices in
  the install folder.
- Client-managed Studio (5.x-8.0): a text license (long base64-like token,
  delivered as `license.txt` / "license key") pasted into Studio at first
  start or obtained automatically from TAC when connecting to a remote
  project. TAC itself stores the license under `Configuration > Licenses` /
  the license page; validation is online against Talend's license server, or
  offline via a generated validation request/response file (menu labels
  (unverified)). Studio caches the license locally; when it expires the
  Studio shows the license dialog again and refuses remote connections.
- Talend 8 Studio for Cloud: login to Talend Cloud / Qlik Talend Cloud
  (region, account/tenant, user or Personal Access Token); entitlement comes
  from the cloud subscription (Named User). Offline token mode exists for
  air-gapped Studio installs (unverified exact label).
- Qlik Community article "Qlik Talend License: A Temporary Extension of an
  End of Life Talend license version" confirms Qlik issues temporary license
  extensions for EOL versions on request (verified title).
- License Types (SDG, verified definitions): Named User (business email;
  not reassignable without written permission); Concurrent User (logged on at
  a point in time to a single Repository = one TAC instance); Admin User
  (TAC/TMC administration only); Concurrent Admin User and Concurrent Consumer
  User (Data Catalog); Engine Token; Cloud Engine; Remote Engine; Per Core
  Limitation (physical/virtual/container cores; ESB runtimes); Per Node
  Limitation; Per Source Limitation (Talend CDC: 1 prod + 1 non-prod key per
  source instance); Production Runtime / Non-Production Runtime (ESB, Data
  Services; Hot Backup counts as production, Warm Backup as non-production);
  Production Server / Non-Production Server (Data Catalog); Rows per Month
  (Stitch); Interactive User (MDM); Commercial Use (OEM); API (API
  Designer/Tester unit).
- Remote Engine entitlements: Gen1 Remote Engine = 9,000 tokens each; Cloud
  Engine = 45,000; a design-only Cloud Engine is bundled with Pipeline
  Designer Standard. Remote Engine Gen2 (Pipeline Designer runtime) is
  provisioned the same way (unverified token cost).
- Component add-ons: SAP, Data Mapper/EBCDIC, Spark, Spark Streaming, DQ and
  ESB are edition features, not separately licensed plug-ins, except
  historically "Talend Data Mapper" and "SAP" packs in 5.x (unverified).
- Generated Code: standalone jobs built from a subscription Studio may be
  run anywhere; "Microservices Generated Code" (Spring Boot ESB artifacts)
  may only run on licensed Remote Engines / Per Core licensed machines
  (verified SDG wording).

## Support tiers

Verified (2021 policy and 2024 SDG): Silver, Gold, Platinum, Mission
Critical.

| Tier | Contacts | Coverage | S1 web ticket response | Phone |
|---|---|---|---|---|
| Silver/Gold | 2 | Regional business hours | 4 h | no |
| Platinum | 4 | Regional business hours | 2 h | yes (2 h ack) |
| Mission Critical | 8 | S1 24x7; other severities 24x5 | 1 h | yes (1 h ack) |

Severities: S1 Blocker, S2 Critical, S3 Major, S4 Minor. Regional hours:
US/Canada 06:00-17:00 PT; EMEA 09:00-18:00 CET; China/Japan/ANZ 09:00-17:00
local. Stitch Standard plan maps to Silver/Gold, Stitch Enterprise to
Platinum. Support excludes trial environments, EOL/Retired beyond period,
modified software, unsupported environments, "how-to" questions, migration
assistance. Under Qlik, cases go through the Qlik Support portal
(community.qlik.com Support) (unverified process detail).

## Upgrade and migration deltas

General rule: import projects into the newer Studio (`Import existing
project` or `Import items`); Studio runs migration tasks per item and bumps
`productVersion` in `talend.project`. Downgrade is impossible; keep a copy.
Remote projects: upgrade TAC first (same monthly level), then Studio; TAC
migrates the project metadata on first connection ("Migration tasks" on the
TAC project page).

### 5.x -> 6.x
- Java 8 required for Studio and generated jobs; Java 7 runtimes can no
  longer execute 6.x code.
- New component framework and Palette reorganisation; some components renamed
  or replaced (e.g. tMysqlInput "Mysql version" lists, tFileInputMSDelimited
  changes) (unverified specifics); Perl generation gone.
- Routines: user routines keep working; system routines updated
  (TalendDate/TalendString signature additions).
- Big Data: MapReduce jobs kept; Spark jobs new; Hadoop distribution lists
  re-cut (CDH 5.x, HDP 2.x).
- TAC: new UI, new DB schema migrated by TAC on start; AMC schema changes.

### 6.x -> 7.x
- Maven-based build everywhere: `pom.xml` generated per job, local `.m2`
  repository inside the Studio (`configuration/.m2`), Nexus 3 as artifact
  repository; "Studio Maven offline" and custom `maven_user_settings.xml`
  settings for proxies.
- TAC "generated jobs" via CommandLine still supported but CI Builder
  (Maven plugin) becomes the recommended pipeline; Nexus 2 still supported in
  7.x, dropped later.
- Big Data: Spark 2 as default; many Hadoop distribution versions removed;
  MapReduce and Pig/Storm deprecated; dynamic distributions (7.1+) to pick
  arbitrary CDH/HDP minor versions (unverified exact versions).
- Logging: 7.3 added log4j2 as the job logging option (project setting);
  log4j 1 remained default (unverified).
- Git: 7.x prefers Git; SVN still available.
- TCK connectors appear next to javajet components (duplicated families in
  the Palette: e.g. tSalesforceInput (legacy) vs the TCK Salesforce).

### 7.x -> 8.0
- Java 11 required for Studio (Zulu OpenJDK recommended); project setting to
  keep generating Java 8-compatible code for execution exists; from R2024-05
  Studio itself needs Java 17, from R2026-06 Java 21; artifacts may still run
  on Java 8/11 (verified Qlik notice).
- SVN removed; Git only (unverified but consistently documented).
- log4j2 only; built jobs ship `log4j2.xml`; custom `log4j.xml` edits must be
  ported; log4j CVE fixes continued through monthly releases (R2022-01
  verified).
- Feature Manager: optional features (Big Data, ESB, DQ, extra connectors)
  are installed from the Talend update site (`update.talend.com` or a TAC/
  Nexus mirror); offline installs need the "update site" zip; CI Builder
  needs `-Dupdatesite.path`.
- Component Kit connectors replace many javajet ones (Salesforce, NetSuite,
  Workday, Marketo, Azure Storage, Google Drive ...); legacy components remain
  as "deprecated" and may be hidden by default in the Palette (unverified
  default).
- Big Data: Pig, Storm and MapReduce jobs removed (unverified); CDH 5.x, HDP
  and MapR distributions dropped; Spark Universal (choose a Spark version,
  supply the cluster config) replaces built-in and dynamic distributions,
  which are deprecated from 8.0 (verified); "Migrate Distribution to..."
  action converts jobs (verified).
- Studio license is still a text token for client-managed; Cloud Studio logs
  in instead.
- Eclipse 4.x base with new dark theme and faster startup; `-clean` on first
  start after patching; `.ini` gains `-Dosgi.requiredJavaVersion=11`
  (unverified exact flag).
- Routines: `routines` dependencies now declared via Maven in
  `Code > Routines > Dependencies`; some third-party jars must be reinstalled
  via "Install external modules" (unverified label).
- TAC 8: new DB migration, `Software update` tab for monthly patches, Nexus
  3 required for shared artifact repository; Job Conductor tasks keep working
  after Studio re-publishes artifacts at the new level.
- Migration guide: help.qlik.com "Talend Migration Guide" 8.0 (URL family
  `.../migration-guide/8.0/...`) lists migration tasks executed on import
  and deprecated components per release (unverified page names).

### TOS 8.0.1 -> subscription 8.0 R-release
- TOS projects import cleanly into a subscription Studio of the same or
  higher level (local project -> remote project via TAC/TMC "import local
  project" or Git push) (unverified wording). Reverse direction fails:
  subscription items (test cases, dynamic schema, CDC, DQ) are unknown to TOS
  and projects saved by a newer monthly release are rejected by TOS 8.0.1
  (`productVersion` too high).

## Documentation and community map

- URL structure (verified examples): `https://help.qlik.com/talend/en-US/<guide-slug>/<version>/<page-slug>`.
  `<version>` is `8.0`, `7.3`, `Cloud`, or a dated Studio doc version such
  as `8.0-R2025-01`. help.talend.com URLs redirect to help.qlik.com/talend
  (old `help.talend.com/r/en-US/8.0/<guide>/<page>` still works via
  redirect).
- Guide slugs seen: `studio-user-guide`, `patch-notes/8.0/<r-label>`,
  `release-notes/8.0/<topic>` (e.g. `r2026-06-cloud-migration-toolkit`,
  `mdm-end-of-life`), `archive-release-notes/8.0/...`,
  `installation-guide-mac/8.0/compatible-operating-systems`,
  `installation-guide-mac/Cloud/compatible-java-environments`,
  `hybrid-installation-guide-linux/Cloud/...`,
  `customer-support-statements/Cloud/product-end-of-life-planning`,
  `customer-support-statements/Cloud/talend-remote-engine-lifecyle` (sic),
  `customer-support-statements/Cloud/tdc-end-of-life-planning`,
  `qlik-talend-cloud-migration-toolkit-user-guide/Cloud/...`,
  `management-console-with-pipeline-designer/Cloud/...`,
  `software-dev-lifecycle-best-practices-guide/7.3/...`,
  `data-catalog-installation-and-upgrade-guide-linux/8.0/...`. Expected
  (unverified slugs): `components` (per component pages), `tac-user-guide`
  ("Talend Administration Center User Guide"), `installation-guide-windows`,
  `installation-guide-linux`, `migration-guide`, `big-data-user-guide`,
  `esb-mediation-components`, `data-quality-...`, `management-console`
  ("Talend Management Console User Guide"), `remote-engine-user-guide`.
- Qlik Cloud-side docs for migration: `https://help.qlik.com/en-US/migration/...`.
- Patch notes mirror: `https://update.talend.com/Studio/8/updates/<R-label>/PATCH_RELEASE_NOTE.html`
  and `.../updates/latest/`.
- Lifecycle: "Talend products lifecycle" page (above), Qlik Community
  "Product Lifecycle" knowledge base, Qlik Community FAQ "Talend 7.3.1 End of
  Support", "Qlik Talend Products: Java 17 Migration Guide", "Talend Data
  Fabric Upgrade Notification: Java 17 compatibility".
- Legal: `https://talend-legal-doc.s3.amazonaws.com/` hosts the Support
  Policy PDF and the Talend Service Description Guide PDF (public). Current
  Qlik agreements at `www.qlik.com/legal-agreements`.
- Community: Talend Community merged into Qlik Community
  (`community.qlik.com`, Talend boards such as "Talend Studio",
  "Installing and Upgrading", "Support Updates", "Official Support Articles").
  Support portal: Qlik Support (cases), formerly Talend Help Center /
  Talend Customer Portal.
- GitHub `github.com/Talend` (public repos; names from memory, unverified
  current state): `tdi-studio-se` (DI Studio plugins, javajet components),
  `tcommon-studio-se` (core/repository), `tbd-studio-se` (Big Data),
  `tesb-studio-se` (ESB), `tdq-studio-se` (Data Quality), `tmdm-studio-se`
  / `tmdm-server-se` (MDM), `components` (legacy TCOMP framework),
  `component-runtime` (Component Kit / TCK, releases on Maven Central as
  `org.talend.sdk.component`), `daikon` (shared libs), `data-prep`,
  `tesb-rt-se` (Talend Runtime), `tcompv0`. Branches historically
  `maintenance/7.3`, `maintenance/8.0`, `master`; tags `release/8.0.1`
  (unverified).
- Downloads: Open Studio historically via talend.com and SourceForge
  (`https://sourceforge.net/projects/talend-studio/`, mirror of TOS builds up
  to 8.0.1); subscription downloads via the Qlik download site / Talend
  Cloud "Downloads" page; monthly patches via Feature Manager.
- Talend Exchange (community components) sunset in the Qlik era; TOS
  component tutorials on `talendforge.org` (historic) (unverified status).

## Qlik-era specifics

- Portfolio naming: "Qlik Talend Cloud" (SaaS), "Qlik Talend Data
  Integration" / "Qlik Talend Data Quality" (capabilities), "Talend Data
  Fabric" (client-managed bundle), "Talend Studio" (desktop), "Talend
  Management Console" (TMC, in Talend Cloud and in Qlik Cloud), "Talend
  Administration Center" (TAC, client-managed), "Qlik Data Gateway - Data
  Movement" (Replicate-based gateway for Qlik Cloud Data Integration; not a
  Talend Remote Engine), "Talend Remote Engine" Gen1 (Studio jobs/routes/
  data services) and Gen2 (Pipeline Designer, datasets, Data Preparation
  connections).
- Qlik Talend Cloud architecture: Qlik Cloud tenant (identity, spaces,
  licensing) hosts TMC and Pipeline Designer; Studio connects by logging in
  with a Qlik account (region + tenant) and publishes artifacts to TMC
  workspaces; execution on Cloud Engines (Qlik-managed) or customer Remote
  Engines; Qlik Cloud Data Integration projects (Replicate-style) run via
  Data Gateway. Legacy Talend Cloud tenants coexist and are migrated
  account-by-account (mandatory for continued TMC access, verified).
- Remote Engine: v2.13+ requires Java 17 (verified); 2.14 current (verified);
  Gen2 monthly (`R2026-03` current, verified).
- Studio Java: 17 mandatory since R2024-05, 21 supported R2025-09 and
  mandatory R2026-06 (verified). Windows ARM / native macOS arm64 builds:
  not confirmed in snippets (unverified; assume x86_64 builds).
- Open Studio: retired 31 Jan 2024; Qlik's page points to Qlik Talend Cloud
  and Talend Data Fabric as the paid paths; TOS 8.0.1 installs keep running
  but receive no fixes.
- 7.3: EOL 30 Nov 2024; paid Limited Extended Support until Dec 2026; after
  that no successor program (third-party claim, unverified).
- TAC and Studio EOL: not announced in any snippet found (unverified
  absence). TAC-to-TMC migration toolkit exists and is actively documented
  (2026).

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| Help page shows a property or component that does not exist in your Studio | help.qlik.com defaults to the latest `8.0-R20xx-xx` Studio doc or `Cloud`; your Studio is older/newer | Pick the version in the page's version selector (`7.3`, `8.0`, dated `8.0-R2025-01`); for Cloud features check TMC release notes by month |
| "Version 8.0.1" reported but behaviour differs between two installs | 8.0.1 is the base build; the monthly R-release is the real version | Compare `Help > About` R-labels and `plugins/*` build dates; align both to the same monthly release |
| Project import rejected: "project created with a newer version" / items fail to open | `talend.project` `productVersion` higher than the Studio, or TOS trying to open subscription items (test cases, dynamic schema, CDC) | Open with the same or newer edition/level; Open Studio can never open items saved by a newer subscription release |
| Studio refuses to connect to TAC: "incompatible version" or jobs fail to publish/deploy after patching | TAC/CommandLine/JobServer not at the same monthly patch as Studio | Patch TAC (`Software update`), CommandLine and JobServer to the identical R-release before patching Studio; patch non-prod first |
| Remote Engine shows "upgrade required"/tasks not deployed after TMC release | TMC moves monthly; old Remote Engine Gen1 (< 2.1x) or Gen2 (only latest monthly is supported) | Upgrade Remote Engine; Gen1 2.13+ needs Java 17 on the engine host |
| Studio starts to a license dialog every time, or "License expired" while TAC shows valid | Studio cached license expired or offline token lapsed; clock skew; Studio cannot reach the license server through proxy | Re-fetch license from TAC/TMC, configure Studio proxy, request a renewed token; for EOL versions ask Qlik Support for a temporary license extension |
| Open Studio download links dead; "retired" page | TOS discontinued 31 Jan 2024; Qlik no longer hosts installers | Use archived 8.0.1 builds (SourceForge mirror) for legacy maintenance only; plan a move to a subscription edition or another tool; no fixes/CVEs will come |
| Studio will not start: "JVM version 11 ... required", or black window on Java 8 | 8.0 needs Java 11 (GA), Java 17 (R2024-05+), Java 21 (R2026-06+); `-vm` points at wrong JDK | Install Zulu/OpenJDK of the required version and set `-vm` in `Talend-Studio-*.ini` above `-vmargs`; re-run with `-clean` |
| Big Data job compile fails after moving Studio to Java 17/21 while cluster is Java 8 | Project code generation level and cluster JDK mismatch; old distribution-specific Spark jobs need Java 8 | Set project settings Java version for generated code to the cluster's level; move jobs to Spark Universal; keep a Java 8/11 JRE on JobServer/Remote Engine for execution (allowed) |
| Old JDBC driver (jTDS for MSSQL, Oracle ojdbc6, DB2 old) throws `IllegalAccessError`/`ClassNotFoundException` under Java 17 | Driver built for Java 8 internals or removed JDK modules | Switch to vendor JDBC drivers compatible with Java 17 (mssql-jdbc, ojdbc11); update the component's driver selection |
| Talend Cloud login fails: "account not found" or tenant not visible | Wrong region (us/us-west/eu/ap/au) or account already migrated to Qlik Cloud | Select the right region, or log in via the Qlik account flow (Studio "Qlik Talend Cloud" option); migrated Talend Cloud accounts must use Qlik login |
| Component missing from Palette that colleague sees | Component availability by license: feature (DQ, Big Data, ESB) not installed via Feature Manager, or edition lacks it (Dynamic schema, CDC, tParallelize, SAP) | Check "Components availability by license"; install the feature; otherwise upgrade edition |
| Deprecated distribution warning / jobs stop compiling after R-release | Built-in or dynamic Hadoop distributions deprecated since 8.0; versions removed over time | Use "Migrate Distribution to..." to Spark Universal; pick the Spark version matching cluster |
| TAC task "start from step" missing after moving to TMC | TMC plans lack mid-plan restart | Redesign plans as smaller tasks or add restart logic in jobs (patterns-gotchas.md) |
| Migrated TAC tasks do nothing in TMC | Migration Toolkit imports tasks paused | Resume each task/plan in TMC to activate triggers |
| `log4j.xml` edits ignored in 8.0 jobs | 8.0 uses log4j2 only | Edit `log4j2.xml` template in Project Settings > Log4j or ship `-Dlog4j2.configurationFile` |
| Studio on RHEL 8.6 does not launch by double-click after R2026-06 | Known issue listed on Compatible OS page | Launch from command line (`./Talend-Studio-linux-gtk-x86_64`) per the page's workaround |
| Nexus 2 repository rejected by Studio 8 / CI Builder | Nexus 2 support dropped in 8.0 (unverified) | Migrate to Nexus 3 or Artifactory |
| SVN project cannot be opened in Studio 8 | SVN support removed (unverified) | Migrate repository to Git (TAC project conversion or re-import local project then push to Git) before upgrading |
| 7.3 CVE fixes stopped arriving | 7.3 EOL 30 Nov 2024; only paid Limited Extended Support until Dec 2026 | Upgrade to 8.0 current monthly; extended support only covers S1 |

## Sources

https://help.qlik.com/talend/en-US/customer-support-statements/Cloud/product-end-of-life-planning
https://help.talend.com/en-US/customer-support-statements/Cloud/product-end-of-life-planning
https://help.qlik.com/talend/en-US/customer-support-statements/Cloud/talend-remote-engine-lifecyle
https://help.qlik.com/talend/en-US/customer-support-statements/Cloud/tdc-end-of-life-planning
https://help.qlik.com/talend/en-us/release-notes/8.0/mdm-end-of-life
https://help.talend.com/en-US/release-notes/7.3/mdm-end-of-life
https://help.qlik.com/talend/en-US/installation-guide-mac/Cloud/compatible-java-environments
https://help.qlik.com/talend/en-US/installation-guide-mac/8.0/compatible-operating-systems
https://help.qlik.com/talend/en-US/hybrid-installation-guide-linux/Cloud/compatible-java-environments-for-hybrid
https://help.qlik.com/talend/en-US/data-catalog-installation-and-upgrade-guide-linux/8.0/compatible-java-runtime-environments
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2025-01/dynamic-support-for-hadoop-distributions-in-talend-studio
https://help.qlik.com/talend/en-US/patch-notes/8.0/fullinstallerrelease801-r2022-10-rt
https://help.qlik.com/talend/en-US/patch-notes/8.0/r2023-08
https://help.qlik.com/talend/en-US/patch-notes/8.0/r2024-08
https://help.qlik.com/talend/en-US/patch-notes/8.0/r2024-11v2
https://help.talend.com/en-US/patch-notes/8.0/r2024-07
https://update.talend.com/Studio/8/updates/R2022-01/PATCH_RELEASE_NOTE.html
https://update.talend.com/studio/8/updates/R2022-03v2/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2022-11/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2024-01/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2024-08/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2024-09/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2024-11/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2024-11v2/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2025-01/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2025-01v2/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2025-03/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2025-08/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2025-09/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2025-09v2/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/latest/PATCH_RELEASE_NOTE.html
https://update.talend.com/Studio/8/updates/R2024-04/messages.properties
https://help.qlik.com/talend/en-US/release-notes/8.0/r2026-06-cloud-migration-toolkit
https://help.qlik.com/talend/en-US/qlik-talend-cloud-migration-toolkit-user-guide/Cloud/migrating-a-task-from-talend-administration-center-to-talend-cloud-management-console
https://help.qlik.com/talend/en-US/hybrid-installation-guide-linux/Cloud/tac-to-tmc-migration
https://help.qlik.com/talend/en-US/archive-release-notes/8.0/r2022-05-talend-cloud-management-console
https://help.qlik.com/talend/en-US/management-console-with-pipeline-designer/Cloud/logging-in-to-talend-cloud-management-console
https://help.qlik.com/en-US/migration/qtcmt-introduction
https://help.qlik.com/en-US/migration/migrating-the-runtime-assets
https://help.qlik.com/en-US/migration/task-artifact-origin
https://help.qlik.com/talend/en-US/software-dev-lifecycle-best-practices-guide/7.3/development-life-cycle-of-product
https://help.talend.com/en-US/software-dev-lifecycle-best-practices-guide/7.3/maintaining
https://community.qlik.com/t5/Official-Support-Articles/Qlik-Talend-Products-Java-17-Migration-Guide/ta-p/2439908
https://community.qlik.com/t5/Support-Updates/Talend-Data-Fabric-Upgrade-Notification-Java-17-compatibility/ba-p/2433315
https://community.qlik.com/t5/Installing-and-Upgrading/Talend-R2024-05-and-Java-17/td-p/2436616
https://community.qlik.com/t5/Official-Support-Articles/Talend-Big-Data-compatibility-with-Zulu-OpenJDK-11/ta-p/2151630
https://community.qlik.com/t5/Official-Support-Articles/FAQ-Talend-7-3-1-End-of-Support/ta-p/2488822
https://community.qlik.com/t5/Official-Support-Articles/Qlik-Talend-License-A-Temporary-Extension-of-an-End-of-Life/ta-p/2460830
https://community.qlik.com/t5/Official-Support-Articles/Talend-On-premises-to-Talend-Cloud-OP2C-migration-FAQs/ta-p/2151385
https://community.qlik.com/t5/Product-Lifecycle/tkb-p/qlik-product-support-lifecycle
https://community.qlik.com/t5/Installing-and-Upgrading/Regarding-Talend-Open-source/td-p/2533229
https://community.qlik.com/t5/Talend-Studio/Talend-Open-Studio-License-Information/td-p/2281668
https://community.qlik.com/t5/Installing-and-Upgrading/Talend-Open-Studio-license/td-p/2395707
https://community.qlik.com/t5/Installing-and-Upgrading/Talend-Open-Studio-8-0-1-Error-Opening-a-job/td-p/2380595
https://community.qlik.com/t5/Installing-and-Upgrading/Unable-to-run-talend-with-another-JDK/td-p/2409032
https://www.qlik.com/us/products/talend-open-studio
https://www.qlik.com/us/news/company/press-room/press-releases/qlik-acquires-talend
https://www.globenewswire.com/news-release/2023/05/16/2670133/0/en/Qlik-Acquires-Talend-Combining-its-Best-in-Class-Data-Integration-with-Talend-s-Leading-Data-Transformation-Quality-and-Governance-Capabilities.html
https://www.talend.com/uk/about-us/press-releases/qlik-completes-acquisition-of-talend/
https://www.techtarget.com/searchdatamanagement/news/366537445/Qlik-completes-purchase-of-Talend-boosts-integration-suite
https://www.techtarget.com/searchbusinessanalytics/news/252497622/Talend-to-be-acquired-by-Thoma-Bravo-for-24-billion
https://siliconangle.com/2021/03/10/talend-sell-private-equity-firm-thoma-bravo-estimated-2-4b-deal/
https://www.financierworldwide.com/talend-taken-private-in-24bn-deal
https://www.houthoff.com/insights/deals-and-matters/thoma-bravo-acquires-talend/
https://www.sec.gov/Archives/edgar/data/1668105/000119312521075675/d137062dex991.htm
https://www.linkedin.com/posts/adeledicoste_update-on-the-future-of-talend-open-studio-activity-7133008327143243776-nw6-
https://www.decivision.com/blog/talend/talend-open-studio-fin-d-une-ere
https://rivery.io/data-learning-center/talend-open-studio-was-discontinued-what-you-need-to-know/
https://www.ksolves.com/blog/big-data/talend-support-ending-dec-2026
https://fr.wikipedia.org/wiki/Talend
https://www.bloorresearch.com/companies/talend/
https://www.computerworld.com/article/1700303/open-enterprise-interview-bertrand-diard-talend-ceo.html
https://www.guru99.com/talend-tutorial.html
https://docs.huihoo.com/talend/6/TalendOpenStudio_BigData_IG_6.0.0_EN.pdf
https://talend-legal-doc.s3.amazonaws.com/Support+Policy+(v2021.03.24)+(English).pdf
https://talend-legal-doc.s3.amazonaws.com/Talend+Service+Description+Guide+(English).pdf
https://repo1.maven.org/maven2/org/talend/sdk/component/component-api/maven-metadata.xml
https://repo1.maven.org/maven2/org/talend/sdk/component/component-runtime/1.2610.0/component-runtime-1.2610.0.pom
https://sourceforge.net/projects/talend-studio/
https://github.com/Talend
