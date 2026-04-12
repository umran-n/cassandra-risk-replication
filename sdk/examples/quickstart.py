from cassandra_risk import CassandraClient

client = CassandraClient()
rsi = client.rsi_latest()

print("Cassandra Risk — Live RSI")
print(f"  RSI Value : {rsi.value:.4f}")
print(f"  Regime    : {rsi.regime}")
print(f"  Position  : {rsi.position_pct:.1f}% of base exposure")
print(f"  Timestamp : {rsi.timestamp}")

signals = client.signals_latest()
print(f"\nGoverned Signals: {len(signals)} active contracts")
for s in signals[:3]:
    print(f"  [{s.structural_theme}] {s.question_text[:60]}...")
    print(f"    P={s.probability_calibrated:.3f}  weight={s.weight:.3f}")
