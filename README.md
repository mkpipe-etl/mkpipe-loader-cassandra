# mkpipe-loader-cassandra

Cassandra loader plugin for [MkPipe](https://github.com/mkpipe-etl/mkpipe). Writes Spark DataFrames into Cassandra tables using `spark-cassandra-connector`.

## Documentation

For more detailed documentation, please visit the [GitHub repository](https://github.com/mkpipe-etl/mkpipe).

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

---

## Connection Configuration

```yaml
connections:
  cassandra_target:
    variant: cassandra
    host: localhost
    port: 9042
    database: my_keyspace
    user: cassandra
    password: cassandra
```

---

## Table Configuration

```yaml
pipelines:
  - name: pg_to_cassandra
    source: pg_source
    destination: cassandra_target
    tables:
      - name: public.events
        target_name: stg_events
        replication_method: full
```

> **Note:** The target table must exist in Cassandra before loading. MkPipe does not create tables automatically.

---

## Write Parallelism

`write_partitions` coalesces the DataFrame to N partitions before writing, reducing the number of concurrent connections to Cassandra:

```yaml
      - name: public.events
        target_name: stg_events
        replication_method: full
        write_partitions: 4
```

### Performance Notes

- Cassandra performs best with a moderate number of concurrent writers. Each Spark partition opens its own connection.
- If you have many Spark executors, `write_partitions: 4–8` reduces connection pressure.
- `coalesce` avoids a shuffle — if you need to *increase* parallelism (e.g. only 1 partition coming in), set a higher value — Cassandra connector will redistribute across nodes.

---

## All Table Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | string | required | Source table name |
| `target_name` | string | required | Cassandra destination table name |
| `replication_method` | `full` / `incremental` | `full` | Replication strategy |
| `write_partitions` | int | — | Coalesce DataFrame to N partitions before writing |
| `dedup_columns` | list | — | Columns used for `mkpipe_id` hash deduplication |
| `tags` | list | `[]` | Tags for selective pipeline execution |
| `pass_on_error` | bool | `false` | Skip table on error instead of failing |
