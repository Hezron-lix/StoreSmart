
function clamp(value, min = 0, max = 1) {
  return Math.min(Math.max(value, min), max);
}

function calculateHealthScore({
  usedStorage,
  totalStorage,
  averageCompressionPercent,
  daysToFull,
}) {
  if (!totalStorage || totalStorage <= 0) {
    throw new Error("Total storage must be greater than zero");
  }

  const capacityScore = clamp(
    1 - usedStorage / totalStorage
  );

  const efficiencyScore = clamp(
    averageCompressionPercent / 100
  );

  const stabilityScore = clamp(
    1 - daysToFull / 365
  );

  const healthScore =
    capacityScore * 0.4 +
    efficiencyScore * 0.3 +
    stabilityScore * 0.3;

  return {
    score: Number(healthScore.toFixed(3)),
    grade: getGrade(healthScore),

    components: {
      capacity: Number(capacityScore.toFixed(3)),
      efficiency: Number(efficiencyScore.toFixed(3)),
      stability: Number(stabilityScore.toFixed(3)),
    },
  };
}

function getGrade(score) {
  if (score >= 0.9) return "A";
  if (score >= 0.8) return "B";
  if (score >= 0.7) return "C";
  if (score >= 0.6) return "D";

  return "F";
}

function calculatePriorityScore(risk, savings) {
  return Number(
    (risk * 0.6 + savings * 0.4).toFixed(2)
  );
}

module.exports = {
  calculateHealthScore,
  calculatePriorityScore,
};