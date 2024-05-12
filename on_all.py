# from pyspark.sql import SparkSession
# from pyspark.sql.functions import col, expr
# from pyspark.ml.feature import MinHashLSH
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from pyspark.ml.feature import MinHashLSH, VectorAssembler
from pyspark.sql.functions import lit

from pyspark.ml.linalg import Vectors
from pyspark.ml.feature import BucketedRandomProjectionLSH, MinHashLSHModel
from pyspark.ml.feature import HashingTF, IDF, Tokenizer

import os

def main(spark, userID):
    '''Main routine for Lab Solutions
    Parameters
    ----------
    spark : SparkSession object
    userID : string, userID of student to find files in HDFS
    '''
    print('Dataframe loading and SQL query')

      # Load the data
    path = f'hdfs:/user/{userID}/'
    ratings = spark.read_csv(path + 'ratings.csv', header=True, inferSchema=True)
    tags = spark.read_csv(path + 'tags.csv', header=True, inferSchema=True)
    movies = spark.read_csv(path + 'movies.csv', header=True, inferSchema=True)
    links = spark.read_csv(path + 'links.csv', header=True, inferSchema=True)
  
    # Merging DataFrames
    movie_ratings = ratings.join(movies.select("movieId", "title"), "movieId", "inner")
    movie_tags = tags.join(movies.select("movieId", "title"), "movieId", "inner")

    rate_history = movie_ratings.union(movie_tags)
  
    # Pivot table to get user-movie matrix
    rate_history_pt = rate_history.groupBy("userId").pivot("title").agg(lit(1)).na.fill(0)
    tokenizer = Tokenizer(inputCol="title", outputCol="tokens")
    hashingTF = HashingTF(numFeatures=1024, inputCol="tokens", outputCol="features")
    rate_history_tf = hashingTF.transform(tokenizer.transform(rate_history))
    
    mh = MinHashLSH(inputCol="features", outputCol="hashes", numHashTables=5)
    model = mh.fit(rate_history_tf)
    
    # Transform features into binary hash buckets
    rate_history_hashed = model.transform(rate_history_tf)
    
    # Find similar pairs
    similar = model.approxSimilarityJoin(rate_history_hashed, rate_history_hashed, 0.6, distCol="JaccardDistance")

    similar = similar.withColumn("userId1", least(col("datasetA.userId"), col("datasetB.userId"))).withColumn("userId2", greatest(col("datasetA.userId"), col("datasetB.userId")))

    similar = similar.filter("datasetA.userId != datasetB.userId")
    similar = similar.dropDuplicates(["userId1", "userId2"])
    similar = similar.select("datasetA.userId", "datasetB.userId", "JaccardDistance").orderBy("JaccardDistance", ascending=False).limit(100)
    similar.show()

if __name__ == "__main__":
    spark = SparkSession.builder.appName('capstone').getOrCreate()
    # spark = SparkSession.builder \
    # .appName('capstone') \
    # .config('spark.executor.memory', '4g') \
    # .config('spark.driver.memory', '4g') \
    # .config('spark.sql.shuffle.partitions', '100') \
    # .config('spark.executor.memoryOverhead', '512m') \
    # .getOrCreate()


    
    userID = os.getenv('USER', 'default_user')  # Default user if not set
    main(spark, userID)
