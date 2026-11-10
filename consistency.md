# Consistency and regional read behavior

The production default is **Available** (`available`); **Local** (`local`) is explicit. Session reads have been removed. [spec.md](spec.md) owns exact behavior. The [AWS spike](spike/README.md) is a legacy experiment, not the revised production API.

## Separate propagation, reads, and scope

| Question | Choices | Meaning |
| --- | --- | --- |
| How do copies propagate? | Active-Active or independent fan-out | Redis handles eventual transport, or the adapter supplies distribution/recovery. |
| How is a value read? | Local; Available (default) | One local candidate, or the first non-null candidate from a concurrent group race including local. |
| Which clusters are searched? | Configured read group | US, EU, or an explicitly configured all-five group; membership is captured for each Available request. |
| Is shared ordering required? | Linearizable (deferred) | Needs a separately designed protocol within geographic/global scope. Group metadata alone is insufficient. |

Neither supported read behavior provides RYOW, newest-value selection, or quorum agreement. Available can return a stale first value; timeout-null means no value arrived in time.

## Infrastructure by consistency level

Local and Available work with Active-Active or independent regional clusters. Active-Active provides CRDT replication and strong eventual convergence; independent clusters require application distribution and recovery. Request-only refresh may leave idle regions stale indefinitely without another write.

Active-Active alone does not provide linearizability. Its possible role as a future replication base is an unvalidated direction; real-time write ordering, safe reads, fencing, partitions, and recovery still require a separate protocol. Independent-cluster linearizable designs remain outside planned scope. There is no implemented linearizable overlay or validated shortcut from replication to strict ordering. See [Redis Active-Active](https://redis.io/docs/latest/operate/rs/databases/active-active/).

## Reference topology

The six independent clients write from these regions. Local reads use their regional database; Available reads fan out to the selected group:

- **US group:** A1/A2 in `us-west-2`, B1 in `us-east-1`, C1 in `us-east-2`.
- **EU group:** D1 in `eu-west-1`, E1 in `eu-central-1`.

Clients do not share application write context or a latest-version directory. Production reads carry no write-dependency context. A1/A2 share one logical regional Redis database in this example, with separate application instances. Actual cell/endpoint placement must be confirmed. Five regional databases with three primary shards each mean fifteen primary shards before replicas; six clients do not mean six databases.

```mermaid
flowchart LR
    subgraph US["US geographic group"]
        subgraph West["us-west-2"]
            A1["A1: read/write; independent client"] --> W["Regional Redis; 3 primary shards"]
            A2["A2: read/write; independent client"] --> W
        end
        subgraph East1["us-east-1"]
            B1["B1: read/write; independent client"] --> U1["Regional Redis; 3 primary shards"]
        end
        subgraph East2["us-east-2"]
            C1["C1: read/write; independent client"] --> U2["Regional Redis; 3 primary shards"]
        end
        W <-->|Data transport| U1
        W <-->|Data transport| U2
        U1 <-->|Data transport| U2
    end
    subgraph EU["EU geographic group"]
        subgraph Ireland["eu-west-1"]
            D1["D1: read/write; independent client"] --> EW["Regional Redis; 3 primary shards"]
        end
        subgraph Frankfurt["eu-central-1"]
            E1["E1: read/write; independent client"] --> EC["Regional Redis; 3 primary shards"]
        end
        EW <-->|Data transport| EC
    end
    US <-->|Asynchronous cross-group data distribution| EU
```

Data transport is Redis Active-Active replication or configured independent adapter fan-out, with durable replay optional. The diagram groups regions; it does not specify physical network routing, synchronous write acknowledgment, or cross-client context sharing. Group names do not select an acknowledgment target set. With baseline local acknowledgment, cross-group distribution is outside the write success path.

## A1 writes 42; readers race within a group

A1 and A2 share the west regional candidate but no cross-client freshness guarantee. B1/C1 read US copies; D1/E1 read EU copies. Propagation may leave a region with an older value or null.

For a US Available read, the adapter queries west, east-1, and east-2 concurrently, including its own local cluster. A local null does not stop the east requests. If east-1 returns 41 before west returns 42, 41 wins. If west returns 42 first, 42 wins. No value comparison or cross-region commit discovery is performed. A later result cannot replace a returned value.

| Replies before deadline | Available result |
| --- | --- |
| Local value first | Return local value immediately. |
| Local null, then a remote value | Return that remote value; early null does not win. |
| A stale value, then a newer value | Return the stale first value. |
| Every member returns null | Return null as soon as the last null arrives. |
| No valid value before deadline, including pending/failed members | Return null at deadline; ignore later values. |

Local queries only its own cluster; it returns the local value or null and never launches remote reads. Local infrastructure errors stay errors. Available validates each candidate, continues past failed attempts, and records all-null separately from deadline-null. Request-level authorization/configuration errors stay errors.

## Read groups and write targets

An Available read group includes local and may be geographic or explicitly global. It does not change the write fan-out target set, write acknowledgment policy, or recovery obligations. US-only reads can coexist with all-five-target writes. The group-racing behavior is explicit; Local has no automatic remote fallback.

## Distribution and history

Request-only mode distributes only the next same-session update's latest version; it need not restore missing historical 42 when 43 is delivered. Local/Available read current candidates without requiring either exact identity. Internal placement verification can still describe a known absent copy as **snapshot missing**. Durable replay optionally retains original copy obligations; neither replay nor all-target placement creates linearizability or proves current authorization.
