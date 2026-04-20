import gc
from datetime import datetime

from pyspark.sql import functions as F
from pyspark.sql.types import TimestampType

from mkpipe.exceptions import ConfigError, LoadError
from mkpipe.models import ConnectionConfig, ExtractResult, TableConfig, WriteStrategy
from mkpipe.spark.base import BaseLoader
from mkpipe.strategy import resolve_write_strategy
from mkpipe.utils import get_logger

JAR_PACKAGES = ['com.datastax.spark:spark-cassandra-connector_2.13:3.5.1']

logger = get_logger(__name__)


class CassandraLoader(BaseLoader, variant='cassandra'):
    def __init__(self, connection: ConnectionConfig):
        self.connection = connection
        self.host = connection.host
        self.port = connection.port or 9042
        self.username = connection.user
        self.password = connection.password
        self.keyspace = connection.database

    def load(self, table: TableConfig, data: ExtractResult, spark) -> None:
        target_name = table.target_name
        df = data.df

        if df is None:
            logger.info({'table': target_name, 'status': 'skipped', 'reason': 'no data'})
            return

        spark.conf.set('spark.cassandra.connection.host', self.host)
        spark.conf.set('spark.cassandra.connection.port', str(self.port))
        if self.username:
            spark.conf.set('spark.cassandra.auth.username', self.username)
        if self.password:
            spark.conf.set('spark.cassandra.auth.password', self.password)

        col_name = self.ingested_at_column
        etl_time = datetime.now()
        if col_name in df.columns:
            df = df.drop(col_name)
        df = df.withColumn(col_name, F.lit(etl_time).cast(TimestampType()))

        if table.write_partitions:
            df = df.coalesce(table.write_partitions)

        strategy = resolve_write_strategy(table, data)

        logger.info({
            'table': target_name,
            'status': 'loading',
            'write_strategy': strategy.value,
        })

        try:
            match strategy:
                case WriteStrategy.APPEND | WriteStrategy.UPSERT:
                    write_mode = 'append'
                case WriteStrategy.REPLACE:
                    write_mode = 'overwrite'
                case _:
                    raise ConfigError(
                        f"Cassandra loader does not support write_strategy: {strategy.value}"
                    )

            (
                df.write.format('org.apache.spark.sql.cassandra')
                .option('keyspace', self.keyspace)
                .option('table', target_name)
                .mode(write_mode)
                .save()
            )
        except (ConfigError, LoadError):
            raise
        except Exception as e:
            raise LoadError(f"Failed to write '{target_name}': {e}") from e

        df.unpersist()
        gc.collect()
        logger.info({'table': target_name, 'status': 'loaded'})
