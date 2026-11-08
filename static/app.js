document.addEventListener("DOMContentLoaded", () => {
  const filter = document.getElementById("account-filter");
  filter.addEventListener("input", () => {
    const query = filter.value.trim().toLowerCase();
    document.querySelectorAll("#balance-sheet-table tbody tr").forEach(row => {
      row.hidden = !row.dataset.account.includes(query);
    });
  });

  if (typeof Chart === "undefined") return;

  const money = (value) => `$${value.toLocaleString(undefined, {maximumFractionDigits: 0})}B`;
  const colors = ["#2878b5", "#48a9c5", "#7fb3d5", "#d9a441", "#5d6d7e", "#8aa6b8"];

  new Chart(document.getElementById("asset-chart"), {
    type: "bar",
    data: {
      labels: window.FDIC_DATA.assetChart.labels,
      datasets: [{data: window.FDIC_DATA.assetChart.values, backgroundColor: colors}]
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: "y",
      plugins: {legend: {display: false}, tooltip: {callbacks: {label: c => money(c.raw)}}},
      scales: {x: {ticks: {callback: value => `$${value / 1000}T`}, grid: {color: "#e7edf1"}}, y: {grid: {display: false}}}
    }
  });

  new Chart(document.getElementById("funding-chart"), {
    type: "doughnut",
    data: {
      labels: window.FDIC_DATA.fundingChart.labels,
      datasets: [{data: window.FDIC_DATA.fundingChart.values, backgroundColor: ["#2878b5", "#d9a441", "#247a50"], borderWidth: 0}]
    },
    options: {responsive: true, maintainAspectRatio: false, cutout: "64%", plugins: {tooltip: {callbacks: {label: c => `${c.label}: ${money(c.raw)}`}}}}
  });
});
