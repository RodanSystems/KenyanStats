"use strict";
const el = id => document.getElementById(id);
let fuel = null;
const money = value => new Intl.NumberFormat("en-KE", {style:"currency",currency:"KES"}).format(value);
function selected() { return fuel?.records.find(row => row.town === el("town").value); }
function renderTown() {
  const row = selected();
  el("fuel-values").replaceChildren();
  if (!row) return;
  for (const [key, label] of [["petrol","Petrol"],["diesel","Diesel"],["kerosene","Kerosene"]]) {
    const wrapper = document.createElement("div"), dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = label; dd.textContent = money(row[key]) + " / litre";
    wrapper.append(dt,dd); el("fuel-values").append(wrapper);
  }
  el("fuel-period").textContent = `Valid ${row.valid_from} to ${row.valid_to}.`;
  el("estimate").textContent = "Submit your distances to calculate a budget.";
}
async function loadFuel() {
  try {
    const response = await fetch("./data/fuel-prices.json", {cache:"no-cache"});
    if (!response.ok) throw new Error("HTTP " + response.status);
    fuel = await response.json();
    if (!Array.isArray(fuel.records) || !fuel.records.length) {
      el("fuel-status").textContent = "Official data is not loaded yet. Run the updater to connect EPRA."; return;
    }
    if (fuel.records.some(r => !r.town || [r.petrol,r.diesel,r.kerosene].some(v => !Number.isFinite(v) || v <= 0))) throw new Error("Invalid data");
    const today = new Intl.DateTimeFormat("en-CA", {timeZone:"Africa/Nairobi",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
    const end = fuel.records[0].valid_to;
    el("fuel-status").textContent = today > end ? "Historical data: the published validity period has ended." : "Official published dataset. Check the validity period below.";
    el("fuel-refreshed").textContent = "Last successful download: " + fuel.fetched_at;
    for (const row of fuel.records) {const option = document.createElement("option");option.value = row.town;option.textContent = row.town;el("town").append(option);}
    el("town").disabled = false;renderTown();
  } catch (error) {el("fuel-status").textContent = "Data could not be loaded. Please consult EPRA directly.";console.error(error);}
}
el("town").addEventListener("change",renderTown);
el("calculator").addEventListener("submit",event => {
  event.preventDefault();const row=selected();if (!row) return;
  const distance=Number(el("distance").value),efficiency=Number(el("efficiency").value),days=Number(el("days").value);
  if (!Number.isFinite(distance) || distance<0 || !Number.isFinite(efficiency) || efficiency<=0 || !Number.isInteger(days) || days<1 || days>31) return;
  el("estimate").textContent = `${money(distance/efficiency*row.petrol)} per day · ${money(distance/efficiency*row.petrol*days)} per month. Fuel only; excludes tolls and maintenance.`;
});
loadFuel();