import gc
from datetime import datetime

from pyspark.sql import functions as F
from pyspark.sql.types import TimestampType

from mkpipe.spark.base import BaseLoader
from mkpipe.models import ConnectionConfig, ExtractResult, TableConfig
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

        etl_time = datetime.now()
        if 'etl_time' in df.columns:
            df = df.drop('etl_time')
        df = df.withColumn('etl_time', F.lit(etl_time).cast(TimestampType()))

        if table.write_partitions:
            df = df.coalesce(table.write_partitions)

        logger.info({'table': target_name, 'status': 'loading'})

        (
            df.write.format('org.apache.spark.sql.cassandra')
            .option('keyspace', self.keyspace)
            .option('table', target_name)
            .mode(data.write_mode)
            .save()
        )

        df.unpersist()
        gc.collect()
        logger.info({'table': target_name, 'status': 'loaded'})
