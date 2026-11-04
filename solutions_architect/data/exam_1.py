exam1 =
 [
    {
        "question_id": {
            "question": "A retail analytics company operates a large-scale data lake on Amazon S3, where they store daily logs of customer transactions, product views, and inventory updates. Each morning, they need to transform and load the data into a data warehouse to support fast analytical queries. The company also wants to enable data analysts to build and train machine learning (ML) models using familiar SQL syntax without writing custom Python code. The architecture must support massively parallel processing (MPP) for fast data aggregation and scoring, and must use serverless AWS services wherever possible to reduce infrastructure management and operational overhead. Which solution best meets these requirements?", 
            "options": {
                "A": "Use a daily AWS Glue job to transform and clean the data stored in Amazon S3. Load the transformed dataset into Amazon Redshift Serverless, which offers MPP capabilities in a serverless model. Enable analysts to use Amazon Redshift ML to build and train ML models", 
                "B": "Provision and run a daily Amazon EMR cluster with Apache Spark to process and transform the S3 data. Load the results into Amazon Redshift (provisioned). Enable ML model development by integrating Redshift with Amazon SageMaker notebooks for advanced modeling tasks",
                "C": "Run a daily AWS Glue job to process and transform the raw files in S3 and register the outputs as Amazon Athena tables in AWS Glue Data Catalog. Allow analysts to build ML models using Amazon Athena ML, with SQL-based predictions on top of S3 data without moving it to a warehouse",
                "D": "Use an AWS Glue job to transform and load data into Amazon RDS for PostgreSQL. Allow analysts to run machine learning models using Amazon Aurora ML integrated with PostgreSQL, leveraging Amazon SageMaker endpoints behind the scenes",
            },
            "correct_option": "A",
            "explanation": "Option A is the best solution because it leverages AWS Glue for ETL processing, Amazon Redshift Serverless for MPP capabilities, and Amazon Redshift ML for building and training ML models using SQL syntax. This architecture minimizes infrastructure management by using serverless services and supports fast analytical queries.",
            "topics": [
                "AWS Glue",
                "Amazon Redshift Serverless",
                "Amazon Redshift ML",
                "MPP",
                "Serverless"
            ],
    

        },
    }
 ]