from collections import Counter

from cassandra_risk import CassandraClient


def count_regime_transitions(history):
    transitions = 0
    previous = None
    for point in history:
        current = point.regime
        if previous is not None and current != previous:
            transitions += 1
        previous = current
    return transitions


client = CassandraClient(enterprise_key="YOUR_ENTERPRISE_KEY")

history = client.rsi_history(days=30)
print("Enterprise RSI history")
for row in history[:5]:
    print(f"  {row.timestamp}: RSI={row.value:.4f} regime={row.regime} position={row.position_pct:.1f}%")

regime_counts = Counter(row.regime for row in history)
print("\nRegime classification counts")
for regime, count in regime_counts.items():
    print(f"  {regime:<10} {count}")
print(f"  transitions: {count_regime_transitions(history)}")

themes = client.themes_latest()
print("\nTheme hazard ranking")
for theme in sorted(themes, key=lambda item: item.hazard_contribution, reverse=True):
    print(
        f"  {theme.theme:<20} hazard={theme.hazard_contribution:.4f} "
        f"share={theme.weight:.3f} probability={theme.probability:.3f}"
    )

theme_history = client.themes_history(days=10)
print(f"\nTheme history rows: {len(theme_history)}")
for row in theme_history[:5]:
    print(f"  {row.timestamp} [{row.theme}] hazard={row.hazard_contribution:.4f}")

families = client.families_latest()
print(f"\nFamily drill-down ({len(families)} families)")
for family in families[:5]:
    print(
        f"  {family.family_id} | agg_p={family.aggregate_probability:.3f} "
        f"| policy={family.aggregation_policy} | contracts={len(family.contracts)}"
    )
    for contract in family.contracts[:1]:
        print(f"    -> {contract.question_text[:80]}...")
