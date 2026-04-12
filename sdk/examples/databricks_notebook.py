# Cassandra Risk — Databricks Integration
# Ready-to-use notebook cells for quant teams
#
# Cell 1: Install
# %pip install cassandra-risk
#
# Cell 2: Free tier — live RSI
from cassandra_risk import CassandraClient

client = CassandraClient()
rsi = client.rsi_latest()
print(f"Live RSI: {rsi.value:.4f} | Regime: {rsi.regime} | Position: {rsi.position_pct:.1f}%")
#
# Cell 3: Enterprise — theme decomposition
# client = CassandraClient(enterprise_key="YOUR_ENTERPRISE_KEY")
# themes = client.themes_latest()
# for t in sorted(themes, key=lambda x: x.hazard_contribution, reverse=True):
#     print(f"{t.theme:<20} P={t.probability:.3f}  hazard={t.hazard_contribution:.4f}")
#
# Cell 4: Enterprise — RSI history as Spark DataFrame
# import pandas as pd
# history = client.rsi_history(days=90)
# df = pd.DataFrame([{"timestamp": r.timestamp, "rsi": r.value,
#                     "regime": r.regime} for r in history])
# spark_df = spark.createDataFrame(df)
# display(spark_df)
