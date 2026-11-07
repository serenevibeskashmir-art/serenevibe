import React, { useState, useEffect, useRef } from "react";
import { apiFetch } from "../api.js";

const UI_THEME = {
  colors: {
    primary: "#1e293b",
    accent: "#0284c7",
    background: "#f8fafc",
    cardBg: "#ffffff",
    border: "#e2e8f0",
    textDark: "#0f172a",
    textLight: "#64748b",
    success: "#10b981",
  },
  shadows: {
    sm: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
    md: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
  }
};

const TRANSIT_OPTIONS = [
  "Airport Pickup and Local Sightseeing: Overnight Srinagar",
  "Airport Pickup: Overnight Pahalgam",
  "Airport Pickup: Overnight Gulmarg",
  "Airport Pickup: Overnight Sonamarg",
  "Srinagar Local Sightseeing: Overnight Srinagar",
  "Srinagar to Gulmarg: Overnight Srinagar",
  "Srinagar to Gulmarg: Overnight Gulmarg",
  "Srinagar to Pahalgam: Overnight Pahalgam",
  "Pahalgam to Srinagar: Overnight Srinagar",
  "Srinagar to Sonamarg: Overnight Srinagar",
  "Srinagar to Sonamarg: Overnight Sonamarg",
  "Pahalgam to Gulmarg: Overnight Pahalgam",
  "Pahalgam to Gulmarg: Overnight Gulmarg",
  "Gulmarg to Pahalgam: Overnight Pahalgam",
  "Gulmarg to Sonamarg: Overnight Srinagar",
  "Gulmarg to Srinagar: Overnight Srinagar",
  "Sonamarg to Gulmarg: Overnight Gulmarg",
  "Pahalgam: Local Sightseeing For 2nd Day",
  "Srinagar to Doodhpathri: Overnight Srinagar",
  "Airport Drop-Departure"
];

const ROUTE_SCHEDULE_TEMPLATES = {
  "Srinagar Local Sightseeing: Overnight Srinagar": [
    { time_slot: "***", description: "Srinagar, the summer capital of Jammu & Kashmir, is known for its Mughal-era gardens and the scenic Dal Lake." },
    { time_slot: "***", description: "Visit famous Mughal Gardens: Nishat Bagh and Shalimar Bagh." },
    { time_slot: "***", description: "Enjoy a relaxing 1-hour Shikara ride on Dal Lake." },
    { time_slot: "***", description: "Explore the historic Shankaracharya Temple for a panoramic city view." }
  ],
  "Srinagar to Gulmarg: Overnight Srinagar": [
    { time_slot: "***", description: "Gulmarg, the Meadow of Flowers, is a hill station famous for its alpine meadows and one of the world's highest cable car rides." },
    { time_slot: "***", description: "Drive from Srinagar to Gulmarg (Meadow of Flowers)." },
    { time_slot: "***", description: "Enjoy the famous Gondola Cable Car Ride (Phase 1 & Phase 2)." },
    { time_slot: "***", description: "Drive back to Srinagar for overnight stay." }
  ],
  "Srinagar to Gulmarg: Overnight Gulmarg": [
    { time_slot: "***", description: "Gulmarg, the Meadow of Flowers, is a hill station famous for its alpine meadows and one of the world's highest cable car rides." },
    { time_slot: "***", description: "Drive from Srinagar to Gulmarg (Meadow of Flowers)." },
    { time_slot: "***", description: "Enjoy the famous Gondola Cable Car Ride (Phase 1 & Phase 2)." },
    { time_slot: "***", description: "Check-in at your Gulmarg hotel and enjoy the night in the bed of flowers." }
  ],
  "Srinagar to Pahalgam: Overnight Pahalgam": [
    { time_slot: "***", description: "Pahalgam, the Valley of Shepherds, is reached via Pampore's saffron fields and the ancient Avantipur temple ruins." },
    { time_slot: "***", description: "Proceed towards Pahalgam past the saffron fields of Pampore, the marvelous ruins of Awantipur and the village of Bijbehara which remains famous as the breadbasket of Kashmir." },
    { time_slot: "***", description: "Check-in at Pahalgam hotel and head out for local sightseeing." },
    { time_slot: "***", description: "Visit Aru Valley, Betaab Valley, and Chandanwari via local cabs." }
  ],
  "Pahalgam: Local Sightseeing For 2nd Day": [
    { time_slot: "***", description: "After breakfast, enjoy the scenic beauty of Pahalgam and take a leisurely walk along the Lidder River." },
    { time_slot: "***", description: "Visit the picturesque Pahalgam market and explore local handicrafts, Kashmiri woollens, and traditional souvenirs." },
    { time_slot: "***", description: "Proceed towards the nearby scenic areas and enjoy breathtaking views of the surrounding pine forests, mountains, and valleys." },
    { time_slot: "***", description: "Later, check out from the hotel and proceed towards Srinagar for your onward journey." }
  ],
  "Pahalgam to Srinagar: Overnight Srinagar": [
    { time_slot: "***", description: "Returning to Srinagar retraces the same scenic saffron-field and riverside route from Pahalgam." },
    { time_slot: "***", description: "Proceed towards Srinagar past the saffron fields of Pampore, the marvelous ruins of Awantipur and the village of Bijbehara which remains famous as the breadbasket of Kashmir." },
    { time_slot: "***", description: "Check-in at Srinagar hotel and head out for local sightseeing." },
    { time_slot: "***", description: "Visit famous Mughal Gardens: Nishat Bagh and Shalimar Bagh." }
  ],
  "Srinagar to Sonamarg: Overnight Srinagar": [
    { time_slot: "***", description: "Sonamarg, the Meadow of Gold, sits along the Sindh River and is the gateway to the Thajiwas Glacier." },
    { time_slot: "***", description: "Day excursion to Sonamarg (Meadow of Gold) along the Sindh River." },
    { time_slot: "***", description: "Visit Thajiwas Glacier via pony or local union vehicle." },
    { time_slot: "***", description: "Return drive back to Srinagar for overnight stay." }
  ],
  "Pahalgam to Gulmarg: Overnight Pahalgam": [
    { time_slot: "***", description: "This route connects the Valley of Shepherds to Gulmarg, the Meadow of Flowers, through scenic Kashmir countryside." },
    { time_slot: "***", description: "Drive from Pahalgam to Gulmarg and enjoy the meadows, mountain views and the famous Gondola ride." },
    { time_slot: "***", description: "Return to your Pahalgam hotel for overnight stay." }
  ],
  "Pahalgam to Gulmarg: Overnight Gulmarg": [
    { time_slot: "***", description: "This route connects the Valley of Shepherds to Gulmarg, the Meadow of Flowers, through scenic Kashmir countryside." },
    { time_slot: "***", description: "Drive from Pahalgam to Gulmarg with short stops along the way." },
    { time_slot: "***", description: "Check in to your Gulmarg hotel and relax for an overnight stay." }
  ],
  "Gulmarg to Sonamarg: Overnight Srinagar": [
    { time_slot: "***", description: "Sonamarg, the Meadow of Gold, is a high-altitude valley surrounded by glaciers and the Sindh River." },
    { time_slot: "***", description: "Drive from Gulmarg to Sonamarg and enjoy the Himalayan scenery, the Sindh River and Thajiwas Glacier." },
    { time_slot: "***", description: "Return to Srinagar in the evening for overnight stay." }
  ],
  "Gulmarg to Srinagar: Overnight Srinagar": [
    { time_slot: "***", description: "Another day to explore Srinagar's beautiful lakes, gardens, heritage sites, and famous attractions at your own pace." },
    { time_slot: "***", description: "Enjoy a peaceful Shikara Ride on the famous Dal Lake and admire the surrounding Himalayan scenery." },
    { time_slot: "***", description: "Explore Mughal Gardens including Nishat Bagh and Shalimar Bagh, followed by a leisurely visit to Pari Mahal." },
    { time_slot: "***", description: "Return to your Srinagar hotel for overnight stay." }
  ],
  "Gulmarg to Pahalgam: Overnight Pahalgam": [
    { time_slot: "***", description: "This route connects Kashmir's premier hill station to the Valley of Shepherds via scenic village roads." },
    { time_slot: "***", description: "Drive from Gulmarg down to Pahalgam via scenic village routes." },
    { time_slot: "***", description: "Explore the local Pahalgam market and riverside walk." }
  ],
  "Airport Pickup and Local Sightseeing: Overnight Srinagar": [
    { time_slot: "Arrival", description: "Your Kashmir journey begins in Srinagar, set on the banks of Dal Lake amid the Mughal gardens." },
    { time_slot: "***", description: "Welcome to Kashmir, Paradise on Earth! Our representative will meet you at the Srinagar International Airport and take you to your hotel." },
    { time_slot: "***", description: "On the beginning of Day-1, you will head out for local sightseeing that includes a visit to the famous Mughal gardens of Nishat and Shalimar, Chashma Shahi Garden and Pari Mahal. You can spend the evening exploring Dal Lake and then head back to your hotel or houseboat for the overnight stay." }
  ],
  "Srinagar to Doodhpathri: Overnight Srinagar": [
    { time_slot: "***", description: "Doodhpathri, the Valley of Milk, is a pristine offbeat meadow fed by the Shaliganga river stream." },
    { time_slot: "***", description: "Drive to Doodhpathri (Valley of Milk), a pristine offbeat meadow." },
    { time_slot: "***", description: "Enjoy walks along the roaring Shaliganga river stream." },
    { time_slot: "***", description: "Drive back to Srinagar." }
  ],
  "Sonamarg to Gulmarg: Overnight Gulmarg": [
    { time_slot: "***", description: "Gulmarg, the Meadow of Flowers, is renowned for its breathtaking Himalayan landscapes, lush meadows, and world-famous attractions." },
    { time_slot: "***", description: "Depart from Sonamarg and enjoy a scenic drive towards Gulmarg through the beautiful Kashmir Valley." },
    { time_slot: "***", description: "Explore Gulmarg's picturesque meadows and enjoy leisure time surrounded by stunning mountain views." },
    { time_slot: "***", description: "Check in to your Gulmarg hotel and relax for an overnight stay." }
  ],
  "Airport Drop-Departure": [
    { time_slot: "Departure", description: "Your Kashmir tour concludes with departure from Srinagar International Airport." },
    { time_slot: "***", description: "Breakfast at hotel and complete check-out formalities." },
    { time_slot: "***", description: "Transfer to Srinagar International Airport for departure flight." }
  ]
};

// ── Tour start / end points ────────────────────────────────────────────────
// Where guests are met on Day 1 and dropped on the last day. Anything other
// than the default is written into the day descriptions and the PDF.
const DEFAULT_POINT = "Srinagar Airport";
const POINT_PRESETS = [
  "Srinagar Airport",
  "Srinagar Railway Station",
  "Jammu Airport",
  "Jammu Tawi Railway Station",
  "Katra Railway Station",
  "Pathankot Railway Station",
];
export const VEHICLE_OPTIONS = ["Sedan", "Ertiga/Innova", "Innova Crysta", "Tempo/Traveler", "Tempo Traveler (17 seater)", "Mini Bus"];
export const MEAL_PLANS = [
  { code: "EP",  name: "European Plan",          desc: "Room only. No meals included." },
  { code: "CP",  name: "Continental Plan",       desc: "Room + Breakfast" },
  { code: "MAP", name: "Modified American Plan", desc: "Room + Breakfast + One major meal (Lunch or Dinner)" },
  { code: "AP",  name: "American Plan",          desc: "Room + Breakfast + Lunch + Dinner (All meals)" },
];
const PICKUP_ROUTE = "Airport Pickup and Local Sightseeing: Overnight Srinagar";
const DROP_ROUTE   = "Airport Drop-Departure";
// Day 1 can end in any base: "Airport Pickup ...: Overnight <City>".
const isPickupRoute = (r) => /^Airport Pickup/i.test(r || "");
const pickupCity = (r) => ((((r || "").match(/Overnight\s+(.+)$/i) || [])[1]) || "").trim() || "Srinagar";
const pickupRouteFor = (city) =>
  /^srinagar$/i.test(city) ? PICKUP_ROUTE : `Airport Pickup: Overnight ${city}`;
const PICKUP_CITY_BLURB = {
  Pahalgam: "Pahalgam, the Valley of Shepherds, sits beside the Lidder River amid pine forests and snow-capped peaks.",
  Gulmarg:  "Gulmarg, the Meadow of Flowers, is known for its Himalayan views, lush meadows and the famous Gondola.",
  Sonamarg: "Sonamarg, the Meadow of Gold, is a high-altitude valley surrounded by glaciers and the Sindh River.",
};
function pickupTemplate(city) {
  return [
    { time_slot: "Arrival", description: PICKUP_CITY_BLURB[city] || `Your Kashmir journey begins with a transfer to ${city}.` },
    { time_slot: "***", description: `Welcome to Kashmir, Paradise on Earth! Our representative will meet you at the Srinagar International Airport and begin your transfer to ${city}.` },
    { time_slot: "***", description: `Enjoy the scenic drive to ${city} with short stops along the way for photos and refreshments.` },
    { time_slot: "***", description: `Check in to your ${city} hotel, relax and enjoy the evening before your overnight stay.` },
  ];
}
const isSrinagarPoint = (p) => /srinagar/i.test(p || "");
const AIRPORT_RE = /Srinagar International Airport|Srinagar Airport/g;

// ── Route picker: "Starting from / Going to / Overnight" ───────────────────
// The day title is generated from three picks, so new combinations never need a new list entry.
const KNOWN_PLACES = ["Srinagar", "Pahalgam", "Gulmarg", "Sonamarg", "Doodhpathri"];  // built into the app
const BASE_NIGHT    = ["Srinagar", "Pahalgam", "Gulmarg", "Sonamarg"];                  // overnight bases built in
// Locations the admin added (name, lat, lon). Filled by loadCustomPlaces(); every picker and the PDF use it.
export const CUSTOM_PLACES = [];
const customNames = () => CUSTOM_PLACES
  .map((p) => p.name)
  .filter((n) => !KNOWN_PLACES.some((k) => k.toLowerCase() === n.toLowerCase()));
const fromOptions  = () => ["Airport", ...BASE_NIGHT, ...customNames()];
const toOptions    = () => ["Local sightseeing", ...BASE_NIGHT, "Doodhpathri", ...customNames(), "Departure"];
const nightOptions = () => [...BASE_NIGHT, ...customNames()];
const isFromPlace  = (name) => fromOptions().includes(name);
const isNightPlace = (name) => nightOptions().includes(name);

function defaultNightFor(to, from) {
  if (isNightPlace(to)) return to;                        // going to a base: sleep there
  if (from === "Airport") return "Srinagar";
  return isNightPlace(from) ? from : "Srinagar";          // sightseeing / day trip: back where you started
}

function routeTitle(from, to, night) {
  if (to === "Departure") return DROP_ROUTE;
  if (!to) return "";
  const n = night || defaultNightFor(to, from);
  if (from === "Airport") {
    return n === "Srinagar" && (to === "Local sightseeing" || to === "Srinagar" || to === "Doodhpathri")
      ? PICKUP_ROUTE
      : `Airport Pickup: Overnight ${n}`;
  }
  if (to === "Local sightseeing") return `${from} Local Sightseeing: Overnight ${n}`;
  return `${from} to ${to}: Overnight ${n}`;
}

// Reverse of routeTitle (null when a stored route isn't one of the generated shapes).
function parseRoute(route) {
  const r = (route || "").trim();
  let m;
  if (r === DROP_ROUTE) return { from: null, to: "Departure", night: "" };
  if ((m = r.match(/^Airport Pickup and Local Sightseeing: Overnight (.+)$/i))) return { from: "Airport", to: "Local sightseeing", night: m[1].trim() };
  if ((m = r.match(/^Airport Pickup: Overnight (.+)$/i)))                       return { from: "Airport", to: m[1].trim(), night: m[1].trim() };
  if ((m = r.match(/^(.+?) Local Sightseeing: Overnight (.+)$/i)))              return { from: m[1].trim(), to: "Local sightseeing", night: m[2].trim() };
  if ((m = r.match(/^(.+?) to (.+?): Overnight (.+)$/i)))                       return { from: m[1].trim(), to: m[2].trim(), night: m[3].trim() };
  return null;
}

// Fallback day text for a generated route that has no hand-written template.
function genericSchedule(route) {
  const p = parseRoute(route);
  if (!p || !p.from || p.to === "Departure") return [];
  if (p.to === "Local sightseeing") {
    return [
      { time_slot: "***", description: `Enjoy a day of local sightseeing around ${p.from}.` },
      { time_slot: "***", description: `Return to your hotel in ${p.night} for overnight stay.` },
    ];
  }
  return [
    { time_slot: "***", description: `Depart from ${p.from} and drive to ${p.to}, enjoying the scenic views along the way.` },
    { time_slot: "***", description: `Explore ${p.to} at leisure.` },
    { time_slot: "***", description: p.night === p.to ? `Check in to your ${p.night} hotel and relax for an overnight stay.` : `Drive to ${p.night} for overnight stay.` },
  ];
}

// Label shown in the route dropdown (the stored route value never changes).
function routeLabel(route, start, end) {
  if (isPickupRoute(route) && start !== DEFAULT_POINT) return route.replace(/^Airport Pickup/, `${start} Pickup`);
  if (route === DROP_ROUTE && end !== DEFAULT_POINT)     return route.replace(/^Airport Drop-Departure/, `${end} Drop-Departure`);
  return route;
}

// Schedule for a route, with the start/end point filled in.
function distText(info) {
  if (!info || !info.km) return "";
  const h = info.hours ? `, about ${info.hours} hrs` : "";
  return ` (approx. ${Math.round(info.km)} km${h})`;
}

// Where this day's travel really starts and ends (Day 1 starts at the tour start point, the last day ends at the end point).
function dayTravel(day, idx, timeline, startPoint, endPoint) {
  const p = parseRoute(day.transit_route);
  const prevNight = idx > 0 ? (timeline[idx - 1]?.overnight_stay || "") : "";
  let from = p?.from || "", to = p?.to || "", kind = "";
  if (!p) {                                            // hand-picked preset: read it from the text
    const m = (day.transit_route || "").match(/^(.+?) to (.+?)(?::|$)/i);
    if (m) { from = m[1]; to = m[2]; }
  }
  if (to === "Departure") { kind = "departure"; from = prevNight || from || "Srinagar"; to = endPoint || DEFAULT_POINT; }
  else if (from === "Airport" || isPickupRoute(day.transit_route)) { kind = "arrival"; from = startPoint || DEFAULT_POINT; to = p?.to === "Local sightseeing" ? (day.overnight_stay || "Srinagar") : (to || day.overnight_stay || "Srinagar"); }
  else if (to === "Local sightseeing") { kind = "local"; to = from; }
  else if (from && to) kind = "transfer";
  return { day_kind: kind, from_place: from, to_place: to };
}

// Short activity title for a generated slot (editable in the box; replaces stale titles from the previous route).
function guessTitle(desc, i) {
  const d = desc || "";
  if (/meet you at|representative will meet/i.test(d))      return "Arrival & Pickup";
  if (/by private cab|road transfer/i.test(d))              return "Road Transfer";
  if (/check in to your|check-in|for overnight stay/i.test(d))                 return "Hotel Check-in & Overnight";
  if (/check-out|breakfast at hotel/i.test(d))              return "Breakfast & Check-out";
  if (/transfer to .*(departure|airport|station)|departure from/i.test(d)) return "Departure Transfer";
  if (/shikara/i.test(d))                                   return "Shikara Ride";
  if (/mughal|nishat|shalimar/i.test(d))                    return "Mughal Gardens";
  if (/^return|return to|drive back/i.test(d))              return "Return to Hotel";
  if (/drive|depart from|travel/i.test(d))                  return "Scenic Drive";
  if (/explore|market|riverside|leisure/i.test(d))          return "Local Exploration";
  return i === 0 ? "Destination Overview" : "Sightseeing";
}

function buildSchedule(route, start, end, startInfo, endInfo) {
  return buildScheduleRaw(route, start, end, startInfo, endInfo)
    .map((x, i) => ({ ...x, activity_title: x.activity_title || guessTitle(x.description, i) }));
}

function buildScheduleRaw(route, start, end, startInfo, endInfo) {
  const city = pickupCity(route);
  const base = (isPickupRoute(route) && city !== "Srinagar"
    ? pickupTemplate(city)
    : (ROUTE_SCHEDULE_TEMPLATES[route] || genericSchedule(route))).map((x) => ({ ...x }));
  if (isPickupRoute(route)) {
    const out = base.map((x) => ({ ...x, description: x.description.replace(AIRPORT_RE, start) }));
    if (!isSrinagarPoint(start)) {
      out.splice(2, 0, { time_slot: "***", description: `From ${start}, travel to ${city === "Srinagar" ? "Srinagar" : "Srinagar and onward to " + city} by private cab${distText(startInfo)} with short breaks en route.` });
    }
    return out;
  }
  if (route === DROP_ROUTE) {
    const kind = /railway/i.test(end) ? "departure train" : /airport/i.test(end) ? "departure flight" : "onward journey";
    return base.map((x) => ({
      ...x,
      description: x.description
        .replace("departure from Srinagar International Airport", `departure from ${end}`)
        .replace(/Transfer to Srinagar International Airport for departure flight\./,
                 isSrinagarPoint(end) ? `Transfer to ${end} for ${kind}.` : `Drive from Srinagar to ${end}${distText(endInfo)} for your ${kind}.`),
    }));
  }
  return base;
}

export const HOTEL_KB = {
  srinagar: [
    {id: "ngm",  name: "Hotel New Green Meadows",       place: "Srinagar", images: []},
    {id: "nclr", name: "New Classic Luxury Resorts",    place: "Srinagar", images: []},
    {id: "hsp",  name: "Hotel Sideeq Palace",           place: "Srinagar", images: []},
    {id: "htv",  name: "Hotel The Victory",             place: "Srinagar", images: []},
    {id: "htk",  name: "Hotel The Karims",              place: "Srinagar", images: []},
    {id: "hgr",  name: "Hotel Gurcoo Residency",        place: "Srinagar", images: []},
    {id: "hdw",  name: "Hotel Deewan",                  place: "Srinagar", images: []},
    {id: "hsd",  name: "Hotel Sadaf",                   place: "Srinagar", images: []},
    {id: "hgm",  name: "Hotel Golden Maple",            place: "Srinagar", images: []},
    {id: "sghb", name: "Srinagar Group of House-Boats", place: "Srinagar", images: []},
    {id: "hicl", name: "Hotel Iceland",                 place: "Srinagar", images: []},
    {id: "hpp",  name: "Hotel Pocket Paradise",         place: "Srinagar", images: []},
    {id: "hlwi", name: "Hotel Lime Wood Inn",           place: "Srinagar", images: []},
    {id: "tsr",  name: "The Shamas Residency",          place: "Srinagar", images: []},
    {id: "wvr",  name: "West View Resorts",             place: "Srinagar", images: []},
  ],
  pahalgam: [
    {id: "hri",  name: "Hotel Riverside Inn",           place: "Pahalgam", images: []},
    {id: "hsr",  name: "Hotel Supreme Resorts",         place: "Pahalgam", images: []},
    {id: "hhr",  name: "Hotel Highland Resorts",        place: "Pahalgam", images: []},
    {id: "hfh",  name: "Hotel Falcon Heights",          place: "Pahalgam", images: []},
    {id: "hlr",  name: "Hotel Lavish Residency",        place: "Pahalgam", images: []},
    {id: "hil",  name: "Hotel Ice Land",                place: "Pahalgam", images: []},
    {id: "her",  name: "Hotel Eden Resorts and Spa",    place: "Pahalgam", images: []},
    {id: "asr",  name: "Asal Resorts",                  place: "Pahalgam", images: []},
  ],
  gulmarg: [
    {id: "hatr", name: "Hotel Apple Tree Resorts",      place: "Gulmarg", images: []},
    {id: "ggr",  name: "Gulmarg Gateway Resorts",       place: "Gulmarg", images: []},
    {id: "hghv", name: "Hotel Grand Hill View",         place: "Gulmarg", images: []},
    {id: "hmsp", name: "Hotel Marina By Stay Pattern",  place: "Gulmarg", images: []},
  ],
  sonamarg: [
    {id: "nrs",  name: "Namrose Resorts",               place: "Sonamarg", images: []},
    {id: "bdr",  name: "Badar Resorts",                 place: "Sonamarg", images: []},
    {id: "cibsp",name: "Country Inn-By Stay Pattern",   place: "Sonamarg", images: []},
    {id: "hmi",  name: "Hotel Mughal India",            place: "Sonamarg", images: []},
  ],
};

// Key of a place in HOTEL_KB: "Pahalgam" -> "pahalgam", "Dal Lake" -> "dal-lake".
export const groupKey = (place = "") => String(place).split(":")[0].trim().toLowerCase().replace(/\s+/g, "-");
function getHotelGroup(overnight_stay = "") {
  return groupKey(overnight_stay) || "srinagar";
}

const ALL_HOTELS_FLAT = Object.values(HOTEL_KB).flat().reduce((acc, h) => {
  acc[h.id] = h;
  return acc;
}, {});

function ensureGroup(place) {
  const g = groupKey(place);
  if (g && !HOTEL_KB[g]) HOTEL_KB[g] = [];
  return g;
}

export function cleanPlaceName(raw) {
  return String(raw || "").replace(/:/g, " ").replace(/\s+/g, " ").trim().slice(0, 40);
}

// AI lookup of a place's coordinates (admin only). Returns {lat, lon} or null. Never throws.
export async function locatePlace(name) {
  try {
    const res = await apiFetch("/api/admin/locate-place", { method: "POST", body: JSON.stringify({ name }) });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.found && Number.isFinite(data.lat) && Number.isFinite(data.lon)) return { lat: data.lat, lon: data.lon };
  } catch { /* optional: the place is still saved without a map position */ }
  return null;
}

// Locations the admin added. Hotels can be attached to any of them.
export async function loadCustomPlaces() {
  try {
    const res = await apiFetch("/api/admin/places");
    if (!res.ok) return;
    const { places = [] } = await res.json();
    CUSTOM_PLACES.length = 0;
    places.filter((p) => !p.builtin).forEach((p) => CUSTOM_PLACES.push({ name: p.name, lat: p.lat, lon: p.lon }));
    CUSTOM_PLACES.forEach((p) => ensureGroup(p.name));
  } catch {
    /* built-in places still work */
  }
}

// Hotels added from the admin "Hotels" tab are merged into HOTEL_KB / ALL_HOTELS_FLAT in place,
// so every picker, the cost dashboard and the photo manager see them without further changes.
export async function loadCustomHotels() {
  await loadCustomPlaces();
  try {
    const res = await apiFetch("/api/admin/hotels");
    if (!res.ok) return;
    const { hotels = [] } = await res.json();
    Object.keys(HOTEL_KB).forEach((g) => {
      HOTEL_KB[g] = HOTEL_KB[g].filter((h) => !h.custom);
    });
    Object.keys(ALL_HOTELS_FLAT).forEach((id) => {
      if (ALL_HOTELS_FLAT[id].custom) delete ALL_HOTELS_FLAT[id];
    });
    hotels.filter((h) => h.custom).forEach((h) => {
      const group = ensureGroup(h.place);
      if (!group) return;
      const hotel = { id: h.id, name: h.name, place: h.place, images: [], custom: true };
      HOTEL_KB[group].push(hotel);
      ALL_HOTELS_FLAT[hotel.id] = hotel;
    });
  } catch {
    /* built-in hotels still work */
  }
}

// ── Hotel Cost Dashboard ───────────────────────────────────────────────────
function calcRowTotal(row) {
  const n  = Number(row.stays)    || 0;
  const r  = Number(row.rooms)    || 0;
  const eb = Number(row.eb)       || 0;
  const rr = Number(row.roomRate) || 0;
  const er = Number(row.ebRate)   || 0;
  return (n * r * rr) + (n * eb * er);
}

function fmtINR(n) {
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

// ── Hotel Image Manager ────────────────────────────────────────────────────
function HotelImageManager() {
  const [hotelImages, setHotelImages]   = useState({});
  const [selectedId,  setSelectedId]    = useState(Object.values(HOTEL_KB).flat()[0]?.id || "");
  const [urlDraft,    setUrlDraft]       = useState("");
  const [uploadFile,  setUploadFile]    = useState(null);
  const [saving,      setSaving]        = useState(false);
  const [loadMsg,     setLoadMsg]       = useState("Loading…");
  const fileInputRef = useRef(null);
  const [, setHotelVer] = useState(0);            // bumps after adding / deleting a hotel so the list redraws
  const [newName,  setNewName]  = useState("");
  const [newPlace, setNewPlace] = useState("Srinagar");
  const [addBusy,  setAddBusy]  = useState(false);
  const [addMsg,   setAddMsg]   = useState(null);

  // Add a hotel right here: it is saved on the server, then shows in the day pickers, PDF and this list.
  const addHotel = async (e) => {
    e?.preventDefault();
    const place = cleanPlaceName(newPlace);
    if (!newName.trim() || !place) return;
    setAddBusy(true); setAddMsg(null);
    try {
      const known = [...KNOWN_PLACES, ...customNames()].some((n) => n.toLowerCase() === place.toLowerCase());
      const loc = known ? null : await locatePlace(place);
      const res = await apiFetch("/api/admin/hotels", { method: "POST", body: JSON.stringify({ name: newName.trim(), place, lat: loc?.lat ?? null, lon: loc?.lon ?? null }) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Could not add the hotel.");
      await loadCustomHotels();
      setSelectedId(data.hotel.id);
      setNewName("");
      setHotelVer((v) => v + 1);
      setAddMsg({ ok: true, text: `"${data.hotel.name}" added to ${data.hotel.place}. Add its photos below.` });
    } catch (err) {
      setAddMsg({ ok: false, text: err.message });
    } finally { setAddBusy(false); }
  };
  const deleteHotel = async () => {
    const h = ALL_HOTELS_FLAT[selectedId];
    if (!h?.custom || !window.confirm(`Delete "${h.name}"? Its saved photos are deleted too.`)) return;
    try {
      const res = await apiFetch(`/api/admin/hotels/${h.id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Delete failed.");
      await loadCustomHotels();
      setSelectedId(Object.values(HOTEL_KB).flat()[0]?.id || "");
      setHotelVer((v) => v + 1);
      setAddMsg({ ok: true, text: `"${h.name}" deleted.` });
    } catch (err) { setAddMsg({ ok: false, text: err.message }); }
  };

  useEffect(() => {
    apiFetch("/api/admin/hotel-images")
      .then((r) => r.json())
      .then((data) => { setHotelImages(data || {}); setLoadMsg(null); })
      .catch(() => setLoadMsg(null));
  }, []);

  const currentImages = hotelImages[selectedId] || [];
  const selectedHotel = ALL_HOTELS_FLAT[selectedId];

  const addUrl = () => {
    const url = urlDraft.trim();
    if (!url) return;
    const updated = { ...hotelImages, [selectedId]: [...currentImages, url] };
    setHotelImages(updated);
    setUrlDraft("");
  };

  // Shrink device photos before storing them. Full-size phone photos are several MB each as base64,
  // which exceeds the server's request limit (Vercel ~4.5 MB) and makes saving fail.
  const compressImage = (file, maxSide = 1280, quality = 0.8) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("Could not read file"));
      reader.onload = () => {
        const img = new Image();
        img.onerror = () => reject(new Error("Not a valid image"));
        img.onload = () => {
          const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
          const canvas = document.createElement("canvas");
          canvas.width = Math.round(img.width * scale);
          canvas.height = Math.round(img.height * scale);
          const ctx = canvas.getContext("2d");
          ctx.fillStyle = "#fff";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          resolve(canvas.toDataURL("image/jpeg", quality));
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });

  const handleFileChange = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    if (!files.length) return;
    try {
      const added = [];
      for (const f of files) added.push(await compressImage(f));
      setHotelImages((prev) => ({ ...prev, [selectedId]: [...(prev[selectedId] || []), ...added] }));
    } catch (err) {
      alert("Could not add photo: " + err.message);
    }
  };

  const removeImage = (idx) => {
    const next = currentImages.filter((_, i) => i !== idx);
    setHotelImages({ ...hotelImages, [selectedId]: next });
  };

  const saveImages = async () => {
    setSaving(true);
    try {
      const res = await apiFetch("/api/admin/hotel-images", {
        method: "POST",
        body: JSON.stringify({ [selectedId]: currentImages }),
      });
      if (res.ok) {
        alert("✅ Images saved for " + selectedHotel?.name);
      } else {
        let detail = "";
        try { detail = (await res.json()).error || ""; } catch { /* non-JSON error page */ }
        if (res.status === 413) detail = "Photos are too large. Remove some photos or use smaller ones.";
        if (res.status === 401) detail = "Session expired — please log in again.";
        alert(`Save failed (${res.status}). ${detail}`.trim());
      }
    } catch {
      alert("Network error while saving.");
    } finally {
      setSaving(false);
    }
  };

  const groupLabels = Object.fromEntries(
    Object.keys(HOTEL_KB).filter((g) => (HOTEL_KB[g] || []).length)
      .map((g) => [g, HOTEL_KB[g][0]?.place || g.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())])
  );
  const allPlaceNames = [...new Set([...KNOWN_PLACES, ...customNames()])];

  return (
    <div style={{ marginTop: "40px", backgroundColor: "#fff", border: "1px solid #e2e8f0", borderRadius: "14px", overflow: "hidden", fontFamily: "system-ui, sans-serif" }}>
      {/* Header: title + add hotel */}
      <div style={{ padding: "14px clamp(14px, 4vw, 24px)", borderBottom: "1px solid #e2e8f0", background: "linear-gradient(135deg, #1e3a4f 0%, #0f2a3a 100%)", color: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px 16px", flexWrap: "wrap", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "1.35rem" }}>🖼️</span>
            <div>
              <p style={{ margin: 0, fontSize: "1rem", fontWeight: "700" }}>Hotels &amp; photos</p>
              <p style={{ margin: "2px 0 0", fontSize: "0.78rem", opacity: 0.75 }}>Add a hotel, then add its photos for the PDF quotation.</p>
            </div>
          </div>
          <form onSubmit={addHotel} style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center", flex: "1 1 360px", justifyContent: "flex-end" }}>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} maxLength={150} placeholder="New hotel name"
              style={{ flex: "2 1 170px", minHeight: "38px", padding: "6px 10px", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "0.85rem", boxSizing: "border-box" }} />
            <input value={newPlace} onChange={(e) => setNewPlace(e.target.value)} list="hpm-places" maxLength={40} placeholder="Place"
              style={{ flex: "1 1 120px", minHeight: "38px", padding: "6px 10px", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "0.85rem", boxSizing: "border-box" }} />
            <datalist id="hpm-places">{allPlaceNames.map((n) => <option key={n} value={n} />)}</datalist>
            <button type="submit" disabled={addBusy || !newName.trim() || !newPlace.trim()}
              style={{ minHeight: "38px", padding: "6px 16px", borderRadius: "8px", border: "none", background: "#0ea5e9", color: "#fff", fontWeight: 700, cursor: addBusy ? "wait" : "pointer", opacity: (!newName.trim() || !newPlace.trim()) ? 0.6 : 1 }}>
              {addBusy ? "Saving…" : "+ Add hotel"}
            </button>
          </form>
        </div>
        {addMsg && <p style={{ margin: "8px 0 0", fontSize: "0.8rem", fontWeight: 600, color: addMsg.ok ? "#86efac" : "#fca5a5" }}>{addMsg.text}</p>}
      </div>

      <div className="hpm-grid">
        {/* Left: hotel list */}
        <div className="hpm-sidebar">
          {Object.entries(groupLabels).map(([groupKey, label]) => (
            <div key={groupKey}>
              <div style={{ padding: "8px 14px", fontSize: "0.7rem", fontWeight: "800", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.6px", backgroundColor: "#f8fafc", borderBottom: "1px solid #f1f5f9" }}>
                📍 {label}
              </div>
              {(HOTEL_KB[groupKey] || []).map((hotel) => {
                const imgCount = (hotelImages[hotel.id] || []).length;
                const isActive = selectedId === hotel.id;
                return (
                  <div
                    key={hotel.id}
                    onClick={() => setSelectedId(hotel.id)}
                    style={{
                      padding: "10px 14px",
                      cursor: "pointer",
                      borderBottom: "1px solid #f1f5f9",
                      backgroundColor: isActive ? "#eff6ff" : "transparent",
                      borderLeft: isActive ? "3px solid #0284c7" : "3px solid transparent",
                      transition: "background 0.12s",
                    }}
                  >
                    <div style={{ fontSize: "0.83rem", fontWeight: isActive ? "700" : "500", color: isActive ? "#1d4ed8" : "#1e293b" }}>
                      {hotel.name}
                    </div>
                    <div style={{ marginTop: "3px", fontSize: "0.7rem", color: imgCount > 0 ? "#10b981" : "#94a3b8", fontWeight: "600" }}>
                      {imgCount > 0 ? `${imgCount} photo${imgCount > 1 ? "s" : ""}` : "No photos yet"}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Right: image editor */}
        <div style={{ padding: "clamp(14px, 4vw, 20px) clamp(14px, 4vw, 24px)" }}>
          {loadMsg ? (
            <p style={{ color: "#94a3b8", fontSize: "0.88rem" }}>{loadMsg}</p>
          ) : (
            <>
              <div style={{ marginBottom: "18px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <h4 style={{ margin: "0 0 4px", fontSize: "1rem", color: "#0f172a", fontWeight: "700" }}>
                  {selectedHotel?.name}
                </h4>
                {selectedHotel?.custom && (
                  <button type="button" onClick={deleteHotel} style={{ padding: "3px 10px", borderRadius: "8px", border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", fontWeight: 600, fontSize: "0.75rem", cursor: "pointer" }}>Delete hotel</button>
                )}
                </div>
                <p style={{ margin: 0, fontSize: "0.78rem", color: "#64748b" }}>
                  📍 {selectedHotel?.place} · {currentImages.length} photo{currentImages.length !== 1 ? "s" : ""} saved
                </p>
              </div>

              {/* Add via URL */}
              <div style={{ display: "flex", gap: "8px", marginBottom: "14px", flexWrap: "wrap" }}>
                <input
                  type="url"
                  placeholder="Paste image URL (https://…)"
                  value={urlDraft}
                  onChange={(e) => setUrlDraft(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addUrl()}
                  style={{ flex: "1 1 180px", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "0.85rem", color: "#0f172a", backgroundColor: "#f8fafc", minHeight: "40px", boxSizing: "border-box" }}
                />
                <button
                  onClick={addUrl}
                  style={{ padding: "8px 16px", backgroundColor: "#0284c7", color: "#fff", border: "none", borderRadius: "8px", fontWeight: "700", fontSize: "0.82rem", cursor: "pointer", whiteSpace: "nowrap", minHeight: "40px" }}
                >
                  + Add URL
                </button>
              </div>

              {/* Add via file upload */}
              <div style={{ marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  style={{ padding: "8px 16px", backgroundColor: "#f1f5f9", color: "#334155", border: "1px solid #cbd5e1", borderRadius: "8px", fontWeight: "600", fontSize: "0.82rem", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: "6px", minHeight: "40px" }}
                >
                  📁 Upload from Device
                </button>
                <input ref={fileInputRef} type="file" accept="image/*" multiple style={{ display: "none" }} onChange={handleFileChange} />
                <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                  JPG, PNG, WEBP — auto-resized before saving
                </span>
              </div>

              {/* Image grid */}
              {currentImages.length === 0 ? (
                <div style={{ textAlign: "center", padding: "40px 20px", backgroundColor: "#f8fafc", borderRadius: "10px", border: "2px dashed #e2e8f0" }}>
                  <div style={{ fontSize: "2rem", marginBottom: "8px" }}>🏔️</div>
                  <p style={{ margin: 0, color: "#94a3b8", fontSize: "0.85rem" }}>No photos yet — add a URL or upload an image above.</p>
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: "12px", marginBottom: "20px" }}>
                  {currentImages.map((src, idx) => (
                    <div key={idx} style={{ position: "relative", borderRadius: "8px", overflow: "hidden", border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.07)" }}>
                      <img
                        src={src}
                        alt={`Hotel photo ${idx + 1}`}
                        style={{ width: "100%", height: "100px", objectFit: "cover", display: "block" }}
                        onError={(e) => { e.target.style.display = "none"; e.target.nextSibling.style.display = "flex"; }}
                      />
                      <div style={{ display: "none", height: "100px", alignItems: "center", justifyContent: "center", backgroundColor: "#f1f5f9", color: "#94a3b8", fontSize: "0.75rem", flexDirection: "column", gap: "4px" }}>
                        <span>⚠️</span><span>Invalid URL</span>
                      </div>
                      <button
                        onClick={() => removeImage(idx)}
                        title="Remove photo"
                        style={{ position: "absolute", top: "5px", right: "5px", width: "22px", height: "22px", borderRadius: "50%", border: "none", backgroundColor: "rgba(220,38,38,0.88)", color: "#fff", cursor: "pointer", fontSize: "0.7rem", fontWeight: "900", display: "flex", alignItems: "center", justifyContent: "center", lineHeight: 1 }}
                      >
                        ✕
                      </button>
                      <div style={{ padding: "4px 6px", fontSize: "0.65rem", color: "#94a3b8", backgroundColor: "#fff", textAlign: "center" }}>
                        Photo {idx + 1}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Save button */}
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button
                  onClick={saveImages}
                  disabled={saving}
                  style={{ padding: "10px 22px", backgroundColor: saving ? "#94a3b8" : "#10b981", color: "#fff", border: "none", borderRadius: "8px", fontWeight: "700", fontSize: "0.88rem", cursor: saving ? "not-allowed" : "pointer", minHeight: "44px" }}
                >
                  {saving ? "Saving…" : "💾 Save Photos for " + (selectedHotel?.name || "Hotel")}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main QuotePreview export ───────────────────────────────────────────────
export default function QuotePreview({ quote, trip }) {
  const [timeline,        setTimeline]        = useState(quote?.itinerary_timeline || []);
  const [activeDay,       setActiveDay]       = useState(0);
  const [editableCost,    setEditableCost]    = useState(quote?.financial_summary?.total_payable_inr || 38500);
  const [hotelSelections, setHotelSelections] = useState({});
  const [, setPlacesVer] = useState(0);                  // bumps when a location is added, so the pickers redraw
  const [addOpen, setAddOpen] = useState(null);          // picker row (1 From, 2 To, 3 Overnight) with the add box open
  const [addText, setAddText] = useState("");
  const [addBusy, setAddBusy] = useState(false);
  const [addErr,  setAddErr]  = useState("");
  const [addNote, setAddNote] = useState("");

  // Saves a new location (AI-located when possible) and uses it for the picker row that asked for it.
  const addCustomPlace = async (raw, onPick) => {
    const name = cleanPlaceName(raw);
    if (!name) return;
    const known = [...KNOWN_PLACES, ...customNames()].find((n) => n.toLowerCase() === name.toLowerCase());
    if (known) { setAddOpen(null); setAddText(""); onPick(known); return; }
    setAddBusy(true); setAddErr(""); setAddNote("");
    try {
      const loc = await locatePlace(name);
      const res = await apiFetch("/api/admin/places", { method: "POST", body: JSON.stringify({ name, lat: loc?.lat ?? null, lon: loc?.lon ?? null }) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Could not add this location.");
      await loadCustomPlaces();
      setPlacesVer((v) => v + 1);
      setAddOpen(null); setAddText("");
      if (!loc) setAddNote(`${data.place.name} was added, but its map position was not found. It appears in the PDF day table, but not as a pin on the map.`);
      onPick(data.place.name);
    } catch (e) {
      setAddErr(e.message);
    } finally {
      setAddBusy(false);
    }
  };
  // Removes a location the admin added. Refused while a day in this quote still uses it.
  const removeCustomPlace = async (name) => {
    const lc = name.toLowerCase();
    const inUse = timeline.some((d) => [d.overnight_stay, d.transit_route].some((v) => (v || "").toLowerCase().includes(lc)));
    if (inUse) { setAddNote(`${name} is used in one of your days. Change that day first, then remove it.`); return; }
    if (!window.confirm(`Remove "${name}" from the location lists?`)) return;
    try {
      const res = await apiFetch("/api/admin/places/" + encodeURIComponent(name), { method: "DELETE" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Could not remove this location.");
      await loadCustomPlaces();
      setPlacesVer((v) => v + 1);
      setAddNote("");
    } catch (e) { setAddNote(e.message); }
  };
  const [startPoint,      setStartPoint]      = useState(quote?.meta_summary?.start_point || DEFAULT_POINT);
  const [endPoint,        setEndPoint]        = useState(quote?.meta_summary?.end_point   || DEFAULT_POINT);

  const [vehicleType, setVehicleType] = useState(quote?.meta_summary?.vehicle_type || quote?.vehicle_type || "Sedan");
  const [mealPlan, setMealPlan] = useState(quote?.meta_summary?.meal_plan || "MAP");   // default MAP
  // Vehicle and meal plan are set in the trip form at the top; changing them there updates this quote.
  useEffect(() => { if (trip?.vehicle) setVehicleType(trip.vehicle); }, [trip?.vehicle]);
  useEffect(() => { if (trip?.meal) setMealPlan(trip.meal); }, [trip?.meal]);
  const [startInfo, setStartInfo] = useState(quote?.meta_summary?.start_info || null);
  const [endInfo,   setEndInfo]   = useState(quote?.meta_summary?.end_info   || null);
  const [locBusy,   setLocBusy]   = useState("");     // "" | "start" | "end"
  const [locMsg,    setLocMsg]    = useState({});     // { start: "...", end: "..." }

  // Re-write the pickup / drop days whenever the start or end point (or its distance) changes.
  const applyPoints = (start, end, sInfo, eInfo) => {
    setTimeline((prev) => prev.map((d) =>
      isPickupRoute(d.transit_route) || d.transit_route === DROP_ROUTE
        ? { ...d, schedule: buildSchedule(d.transit_route, start, end, sInfo, eInfo) }
        : d));
  };
  // Route picker: one apply path shared by presets and the From / To / Overnight chips.
  const [pickDraft, setPickDraft] = useState({});     // unfinished picks per day index
  const applyRoute = (route, idx = activeDay) => {
    const automaticSchedule = buildSchedule(route, startPoint, endPoint, startInfo, endInfo);
    const overnightMatch = route.match(/Overnight\s+(.+)$/i);
    const derivedCity = overnightMatch ? overnightMatch[1].trim() : null;
    if (derivedCity) {
      const hotelGroup = HOTEL_KB[groupKey(derivedCity)] || [];
      setHotelSelections(prev => ({ ...prev, [idx]: hotelGroup[0]?.id || null }));
    } else {
      setHotelSelections(prev => ({ ...prev, [idx]: null }));
    }
    setTimeline(prev => {
      const next = [...prev];
      if (next[idx]) {
        next[idx] = { ...next[idx], transit_route: route, title: route, schedule: automaticSchedule, ...(derivedCity && { overnight_stay: derivedCity }) };
      }
      return next;
    });
    setPickDraft(prev => { const n = { ...prev }; delete n[idx]; return n; });
  };
  const changeStart = (v) => { setStartPoint(v); setStartInfo(null); setLocMsg((m) => ({ ...m, start: "" })); applyPoints(v, endPoint, null, endInfo); };
  const changeEnd   = (v) => { setEndPoint(v);   setEndInfo(null);   setLocMsg((m) => ({ ...m, end: "" }));   applyPoints(startPoint, v, startInfo, null); };

  // Ask the AI for coordinates + road distance (admin-only endpoint). The numbers stay editable.
  const locatePoint = async (which) => {
    const name = (which === "start" ? startPoint : endPoint) || "";
    setLocBusy(which); setLocMsg((m) => ({ ...m, [which]: "" }));
    try {
      const res = await apiFetch("/api/admin/locate-place", { method: "POST", body: JSON.stringify({ name }) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Lookup failed");
      if (!data.found) { setLocMsg((m) => ({ ...m, [which]: data.message || "Not found." })); }
      else {
        const info = { lat: data.lat, lon: data.lon, km: data.road_km, hours: data.drive_hours };
        if (which === "start") { setStartInfo(info); applyPoints(startPoint, endPoint, info, endInfo); }
        else                   { setEndInfo(info);   applyPoints(startPoint, endPoint, startInfo, info); }
        setLocMsg((m) => ({ ...m, [which]: "Estimated by AI. Please check the numbers." }));
      }
    } catch (e) { setLocMsg((m) => ({ ...m, [which]: e.message })); }
    setLocBusy("");
  };
  const editInfo = (which, field, value) => {
    const setter = which === "start" ? setStartInfo : setEndInfo;
    const cur = (which === "start" ? startInfo : endInfo) || {};
    const next = { ...cur, [field]: value === "" ? null : Number(value) };
    setter(next);
    applyPoints(startPoint, endPoint, which === "start" ? next : startInfo, which === "end" ? next : endInfo);
  };

  // ── AI description writer (admin-only endpoint, same key as the website chatbot) ──
  const [aiHints, setAiHints] = useState("");
  const [aiBusy,  setAiBusy]  = useState("");   // "" | "day" | "act-<index>"
  const [aiError, setAiError] = useState("");

  const describeCall = async (mode, extra = {}) => {
    const day = timeline[activeDay] || {};
    const res = await apiFetch("/api/admin/describe-itinerary", {
      method: "POST",
      body: JSON.stringify({
        mode,
        day_number: day.day || activeDay + 1,
        total_days: timeline.length,
        route: day.transit_route || day.title || "",
        ...dayTravel(day, activeDay, timeline, startPoint, endPoint),
        overnight: day.overnight_stay || "",
        start_point: startPoint || DEFAULT_POINT,
        end_point: endPoint || DEFAULT_POINT,
        hints: aiHints,
        ...extra,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "AI request failed");
    return data.items || [];
  };

  const aiWriteActivity = async (actIdx) => {
    const slot = timeline[activeDay]?.schedule?.[actIdx];
    if (!slot) return;
    setAiBusy("act-" + actIdx); setAiError("");
    try {
      const [item] = await describeCall("activity", {
        activity_title: slot.activity_title || "",
        time_slot: slot.time_slot || "",
        current_text: slot.description || "",
      });
      if (item) {
        setTimeline((prev) => prev.map((d, i) => i !== activeDay ? d : {
          ...d,
          schedule: d.schedule.map((x, j) => j !== actIdx ? x : {
            ...x,
            description: item.description,
            ...(item.activity_title && !x.activity_title ? { activity_title: item.activity_title } : {}),
          }),
        }));
      }
    } catch (e) { setAiError(e.message); }
    setAiBusy("");
  };

  const aiRewriteDay = async () => {
    const day = timeline[activeDay];
    if (!day) return;
    if ((day.schedule || []).length && !window.confirm("Replace all activities for this day with AI-written ones?")) return;
    setAiBusy("day"); setAiError("");
    try {
      const items = await describeCall("day");
      setTimeline((prev) => prev.map((d, i) => i !== activeDay ? d : {
        ...d,
        schedule: items.map((it) => ({ time_slot: "***", activity_title: it.activity_title || "", description: it.description })),
      }));
    } catch (e) { setAiError(e.message); }
    setAiBusy("");
  };

  useEffect(() => {
    if (quote?.financial_summary?.total_payable_inr) setEditableCost(quote.financial_summary.total_payable_inr);
  }, [quote]);

  useEffect(() => {
    if (quote?.itinerary_timeline) {
      hist.current = { past: [], future: [], last: { timeline: quote.itinerary_timeline, hotelSelections: {} }, restoring: false };
      setTimeline(quote.itinerary_timeline); setActiveDay(0);
    }
  }, [quote]);

  // ── Builder tools: day management, checks, undo / redo, autosave ──────────
  const isDepDay = (d) => !!d && (d.transit_route === DROP_ROUTE || String(d.overnight_stay || "").toLowerCase() === "departure");
  const flatHotels = ALL_HOTELS_FLAT;

  const rebuildDays = (order, target) => {
    // order = old day indexes in their new positions (a repeated index is a copy)
    const nextDays = order.map((o, k) => {
      const d = JSON.parse(JSON.stringify(timeline[o]));
      d.day = k + 1;
      if (/^Day \d+ Plan$/.test(d.date || "")) d.date = `Day ${k + 1} Plan`;
      return d;
    });
    const nextSel = {};
    order.forEach((o, k) => { if (hotelSelections[o]) nextSel[k] = hotelSelections[o]; });
    setTimeline(nextDays);
    setHotelSelections(nextSel);
    setPickDraft({});
    setActiveDay(Math.max(0, Math.min(target, nextDays.length - 1)));
  };
  const range = (n) => Array.from({ length: n }, (_, i) => i);
  const moveDay = (i, dir) => {
    const j = i + dir;
    if (j < 0 || j >= timeline.length) return;
    const order = range(timeline.length);
    [order[i], order[j]] = [order[j], order[i]];
    rebuildDays(order, j);
  };
  const copyDay = (i) => { const o = range(timeline.length); o.splice(i + 1, 0, i); rebuildDays(o, i + 1); };
  const deleteDay = (i) => {
    if (timeline.length <= 1) return;
    if (!window.confirm(`Delete Day ${i + 1}? You can bring it back with Undo.`)) return;
    rebuildDays(range(timeline.length).filter((k) => k !== i), activeDay > i ? activeDay - 1 : activeDay);
  };
  const addDay = () => {
    const last = timeline[timeline.length - 1];
    const n = timeline.length + 1;
    const night = last && !isDepDay(last) && last.overnight_stay ? last.overnight_stay : "Srinagar";
    setTimeline((prev) => [...prev, { day: n, title: "", date: `Day ${n} Plan`, transit_route: "", overnight_stay: night, schedule: [], ...(last && last.rooms != null ? { rooms: last.rooms } : {}), ...(last && last.eb != null ? { eb: last.eb } : {}) }]);
    setActiveDay(n - 1);
    setPickDraft({});
  };

  const shortRoute = (d) => {
    const p = parseRoute(d.transit_route);
    if (d.transit_route === DROP_ROUTE) return "Departure";
    if (p && p.from === "Airport") return p.to === "Local sightseeing" ? "Airport pickup" : `Airport to ${p.to}`;
    if (p && p.to === "Local sightseeing") return `${p.from} sightseeing`;
    if (p) return `${p.from} to ${p.to}`;
    return d.title || "No route yet";
  };

  // Checks shown above the day editor; most come with a one-click fix.
  const issues = (() => {
    const out = [];
    const n = timeline.length;
    timeline.forEach((day, i) => {
      const no = i + 1, dep = isDepDay(day);
      const open = () => setActiveDay(i);
      if (!day.transit_route && !dep) out.push({ day: i, text: `Day ${no}: no route chosen yet.`, btn: "Open day", fix: open });
      if (!dep && day.overnight_stay && !hotelSelections[i]) {
        const g = HOTEL_KB[getHotelGroup(day.overnight_stay)] || [];
        out.push({ day: i, text: `Day ${no}: no hotel chosen in ${day.overnight_stay}.`, btn: g.length ? "Pick suggested hotel" : "Open day",
          fix: g.length ? () => setHotelSelections((prev) => ({ ...prev, [i]: g[0].id })) : open });
      }
      const p = parseRoute(day.transit_route);
      if (i > 0 && p && p.from && p.from !== "Airport") {
        const prev = timeline[i - 1];
        if (!isDepDay(prev) && prev.overnight_stay && prev.overnight_stay.toLowerCase() !== p.from.toLowerCase()) {
          const canFix = isFromPlace(prev.overnight_stay) && p.to !== "Departure";
          out.push({ day: i, text: `Day ${no} starts from ${p.from}, but Day ${i} ended in ${prev.overnight_stay}.`,
            btn: canFix ? `Start from ${prev.overnight_stay}` : "Open day",
            fix: canFix ? () => applyRoute(routeTitle(prev.overnight_stay, p.to, p.night), i) : open });
        }
      }
      if ((day.schedule || []).some((x) => !String(x.description || "").trim()))
        out.push({ day: i, text: `Day ${no}: an activity has no description.`, btn: "Open day", fix: open });
    });
    if (n && !isDepDay(timeline[n - 1])) {
      out.push({ day: n - 1, text: "The last day is not a departure day.", btn: "Make it departure",
        fix: () => { applyRoute(DROP_ROUTE, n - 1); setTimeline((prev) => prev.map((d, k) => k === n - 1 ? { ...d, overnight_stay: "Departure" } : d)); } });
    }
    return out;
  })();
  const warnDays = new Set(issues.map((x) => x.day));
  const [showChecks, setShowChecks] = useState(false);
  const setDayField = (i, field, value) => setTimeline((prev) => prev.map((d, k) => (k === i ? { ...d, [field]: value } : d)));
  // Rooms / extra beds: changing a day also sets the same number on every day after it (so Day 1 sets the whole trip).
  const setRoomField = (i, field, value) => setTimeline((prev) => prev.map((d, k) => (k >= i ? { ...d, [field]: value } : d)));
  // One click: give every day without a hotel the first suggested hotel for its overnight city.
  const missingHotelDays = timeline.map((d, i) => i).filter((i) => {
    const d = timeline[i];
    return !isDepDay(d) && d.overnight_stay && !hotelSelections[i] && (HOTEL_KB[getHotelGroup(d.overnight_stay)] || []).length > 0;
  });
  const fixAllHotels = () => setHotelSelections((prev) => {
    const next = { ...prev };
    missingHotelDays.forEach((i) => { next[i] = HOTEL_KB[getHotelGroup(timeline[i].overnight_stay)][0].id; });
    return next;
  });

  // Undo / redo: edits are grouped (0.6 s) into history steps; a draft is also kept in this browser.
  const hist = useRef({ past: [], future: [], last: null, restoring: false });
  const [, setHistTick] = useState(0);
  const [saveState, setSaveState] = useState("saved");
  const [draftOffer, setDraftOffer] = useState(null);
  const draftKey = "qp-draft:" + (quote?.meta_summary?.client_name || "client");
  const saveDraft = (snap) => {
    try {
      localStorage.setItem(draftKey, JSON.stringify({ ...snap, startPoint, endPoint, editableCost, vehicleType, mealPlan, at: Date.now() }));
    } catch (e) { /* storage unavailable: undo still works */ }
  };
  useEffect(() => {
    const h = hist.current;
    const snap = { timeline, hotelSelections };
    if (h.restoring) { h.restoring = false; h.last = snap; return; }
    if (!h.last) { h.last = snap; return; }
    if (JSON.stringify(h.last) === JSON.stringify(snap)) return;
    setSaveState("saving");
    const t = setTimeout(() => {
      h.past.push(h.last);
      if (h.past.length > 40) h.past.shift();
      h.future = [];
      h.last = snap;
      saveDraft(snap);
      setSaveState("saved");
      setHistTick((x) => x + 1);
    }, 600);
    return () => clearTimeout(t);
  }, [timeline, hotelSelections]);

  const restoreSnap = (target) => {
    hist.current.restoring = true;
    setTimeline(target.timeline);
    setHotelSelections(target.hotelSelections);
    setPickDraft({});
    setActiveDay((a) => Math.max(0, Math.min(a, target.timeline.length - 1)));
    setSaveState("saved");
    setHistTick((x) => x + 1);
  };
  const undo = () => {
    const h = hist.current, cur = { timeline, hotelSelections };
    if (h.last && JSON.stringify(cur) !== JSON.stringify(h.last)) { h.future.unshift(cur); restoreSnap(h.last); return; }
    if (!h.past.length) return;
    const target = h.past.pop();
    h.future.unshift(cur); h.last = target;
    restoreSnap(target);
  };
  const redo = () => {
    const h = hist.current;
    if (!h.future.length) return;
    const next = h.future.shift();
    h.past.push({ timeline, hotelSelections }); h.last = next;
    restoreSnap(next);
  };
  const canUndo = hist.current.past.length > 0 || saveState === "saving";
  const canRedo = hist.current.future.length > 0;

  useEffect(() => {
    try {
      const raw = localStorage.getItem(draftKey);
      if (!raw) return;
      const d = JSON.parse(raw);
      const base = JSON.stringify(quote?.itinerary_timeline || []);
      if (d && Array.isArray(d.timeline) && JSON.stringify(d.timeline) !== base) setDraftOffer(d);
    } catch (e) { /* ignore */ }
  }, [draftKey]);
  const restoreDraft = () => {
    const d = draftOffer;
    if (!d) return;
    setTimeline(d.timeline);
    setHotelSelections(d.hotelSelections || {});
    if (d.startPoint) setStartPoint(d.startPoint);
    if (d.endPoint) setEndPoint(d.endPoint);
    if (d.editableCost) setEditableCost(d.editableCost);
    if (d.vehicleType) setVehicleType(d.vehicleType);
    if (d.mealPlan) setMealPlan(d.mealPlan);
    setActiveDay(0); setPickDraft({}); setDraftOffer(null);
  };
  const discardDraft = () => { try { localStorage.removeItem(draftKey); } catch (e) { /* ignore */ } setDraftOffer(null); };

  const generateChecked = async () => {
    if (issues.length && !window.confirm(`${issues.length} item(s) still need attention:\n\n` + issues.slice(0, 6).map((x) => "• " + x.text).join("\n") + "\n\nGenerate the PDF anyway?")) return;
    await generatePdf();
  };

  // ── PDF export (shared by the sticky bar and the footer button) ──
  const [pdfBusy, setPdfBusy] = useState(false);
  const generatePdf = async () => {
    setPdfBusy(true);
              try {
                const currentClientName = quote?.meta_summary?.client_name || "Client";
                const printRes = await apiFetch("/api/itinerary/generate", {
                  method: "POST",
                  body: JSON.stringify({
                    client_name: currentClientName,
                    client_email: quote?.meta_summary?.client_email || "",
                    days: timeline.length || quote?.meta_summary?.total_days || 5,
                    start_date: quote?.meta_summary?.start_date || quote?.start_date || "Flexible",
                    adults: quote?.meta_summary?.adults || quote?.adults || 2,
                    kids: quote?.meta_summary?.kids ?? quote?.kids ?? 0,
                    budget_tier: quote?.meta_summary?.budget_tier || "Mid-Range",
                    trip_pace: quote?.meta_summary?.trip_pace || "Moderate",
                    custom_cost: editableCost,
                    vehicle_type: vehicleType,
                    meal_plan: mealPlan,
                    return_pdf: true,
                    timeline,
                    hotelSelections,
                    hotel_details: Object.values(hotelSelections).reduce((acc, id) => {
                      const h = ALL_HOTELS_FLAT[id];
                      if (h) acc[id] = { name: h.name, place: h.place };
                      return acc;
                    }, {}),
                    start_info: startInfo,
                    end_info: endInfo,
                    start_point: (startPoint || "").trim() || DEFAULT_POINT,
                    end_point: (endPoint || "").trim() || DEFAULT_POINT,
                  }),
                });
                const isPdf = (printRes.headers.get("content-type") || "").includes("application/pdf");
                if (printRes.ok && isPdf) {
                  const safeName = currentClientName.replace(/ /g, "_");
                  const fileName = "Kashmir_Tour_" + safeName + ".pdf";
                  const fileBlob = await printRes.blob();
                  const blobUrl  = window.URL.createObjectURL(fileBlob);
                  const link     = document.createElement("a");
                  link.href      = blobUrl;
                  link.setAttribute("download", fileName);
                  document.body.appendChild(link);
                  link.click();
                  document.body.removeChild(link);
                  window.URL.revokeObjectURL(blobUrl);
                } else {
                  let msg = "";
                  try { msg = (await printRes.json()).error || ""; } catch (e) { /* not JSON */ }
                  alert("PDF could not be generated" + (msg ? ": " + msg : ".") + " Please try again.");
                }
              } catch (err) {
                console.error(err);
                alert("System Interface Error: Script logic execution crashed.");
              }
    setPdfBusy(false);
  };

  const handleDescriptionChange = (dayIndex, activityIndex, newValue) => {
    const updatedTimeline = [...timeline];
    updatedTimeline[dayIndex].schedule[activityIndex].description = newValue;
    setTimeline(updatedTimeline);
  };

  return (
    <>
      <style>{`
        .qp-wrap {
          padding: clamp(14px, 4vw, 24px);
          background: ${UI_THEME.colors.background};
          min-height: 100vh;
          font-family: system-ui, sans-serif;
          box-sizing: border-box;
        }
        .qp-meta-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 16px;
          background: ${UI_THEME.colors.cardBg};
          padding: 16px 20px;
          border-radius: 12px;
          box-shadow: ${UI_THEME.shadows.sm};
          border: 1px solid ${UI_THEME.colors.border};
          margin-bottom: 24px;
        }
        .qp-active-day {
          padding: clamp(14px, 4vw, 20px);
          background: #f8fafc;
          border-radius: 6px;
          border: 1px solid #e2e8f0;
        }
        .qp-route-select {
          width: 100%;
          max-width: 480px;
          padding: 8px 12px;
          border-radius: 6px;
          border: 1px solid #cbd5e1;
          background: #fff;
          font-size: 0.9rem;
          color: #1e293b;
          cursor: pointer;
          box-sizing: border-box;
        }
        .qp-hotel-select {
          width: 100%;
          max-width: 480px;
          padding: 8px 12px;
          border-radius: 6px;
          border: 1px solid #cbd5e1;
          background: #fff;
          font-size: 0.85rem;
          font-weight: 500;
          color: #1e293b;
          cursor: pointer;
          box-sizing: border-box;
        }
        .qp-city-btns {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 8px;
        }
        .qp-activity-row {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 8px;
          flex-wrap: wrap;
        }
        .qp-time-input {
          padding: 4px 8px;
          width: 90px;
          border: 1px solid #cbd5e1;
          border-radius: 4px;
          min-height: 36px;
          box-sizing: border-box;
          flex-shrink: 0;
        }
        .qp-title-input {
          padding: 4px 8px;
          flex: 1;
          min-width: 120px;
          border: 1px solid #cbd5e1;
          border-radius: 4px;
          min-height: 36px;
          box-sizing: border-box;
        }
        .qp-sticky { position: sticky; top: 0; z-index: 30; display: flex; flex-wrap: wrap; align-items: center; gap: 10px 22px;
          background: #0f172a; color: #fff; padding: 12px 18px; border-radius: 12px; margin-bottom: 18px; box-shadow: ${UI_THEME.shadows.md}; }
        .qp-sticky .k { font-size: 0.68rem; letter-spacing: .06em; text-transform: uppercase; color: #cbd5e1; }
        .qp-sticky .v { font-size: 0.95rem; font-weight: 700; }
        .qp-sticky .grow { flex: 1 1 120px; font-size: 0.8rem; color: #cbd5e1; }
        .qp-ghost { border: 1px solid #475569; background: transparent; color: #fff; border-radius: 8px; min-height: 40px; padding: 0 14px; font-weight: 600; cursor: pointer; }
        .qp-ghost:disabled { opacity: .4; cursor: not-allowed; }
        .qp-gen { border: 0; background: #b4690a; color: #fff; border-radius: 8px; min-height: 40px; padding: 0 18px; font-weight: 700; cursor: pointer; }
        .qp-gen:disabled { opacity: .6; cursor: wait; }
        .qp-badge { display: inline-block; background: #fbbf24; color: #1c1917; border-radius: 999px; font-size: 0.72rem; font-weight: 800; padding: 2px 9px; margin-left: 8px; }
        .qp-badge.ok { background: #4ade80; color: #052e16; }
        .qp-ov { display: flex; gap: 12px; overflow-x: auto; padding: 4px 4px 12px; margin-bottom: 8px; }
        .qp-ovcard { background: #fff; border: 2px solid #e2e8f0; border-radius: 12px; flex: 0 0 160px; display: flex; flex-direction: column; overflow: hidden; }
        .qp-ovcard.on { border-color: #2563eb; box-shadow: 0 0 0 3px #dbeafe; }
        .qp-ovmain { all: unset; box-sizing: border-box; display: flex; flex-direction: column; gap: 6px; padding: 12px; cursor: pointer; min-height: 108px; flex: 1 1 auto; }
        .qp-ovmain:focus-visible { outline: 3px solid #2563eb; outline-offset: -3px; }
        .qp-ovdn { font-size: 0.72rem; font-weight: 800; color: #475569; letter-spacing: .05em; text-transform: uppercase; display: flex; justify-content: space-between; align-items: center; }
        .qp-ovrt { font-size: 0.92rem; font-weight: 800; line-height: 1.25; color: #0f172a; }
        .qp-ovnt { font-size: 0.8rem; color: #334155; }
        .qp-ovhot { font-size: 0.74rem; font-weight: 700; border-radius: 6px; padding: 3px 7px; background: #e0f2fe; color: #075985; align-self: flex-start; }
        .qp-ovhot.bad { background: #fee2e2; color: #991b1b; }
        .qp-ovdot { width: 10px; height: 10px; border-radius: 50%; background: #f59e0b; }
        .qp-ovacts { display: flex; border-top: 1px solid #e2e8f0; }
        .qp-ovacts button { flex: 1; border: 0; border-right: 1px solid #e2e8f0; background: #f8fafc; color: #334155; min-height: 40px; font-size: 0.78rem; font-weight: 700; cursor: pointer; }
        .qp-ovacts button:last-child { border-right: 0; }
        .qp-ovacts button:hover:not(:disabled) { background: #e2e8f0; }
        .qp-ovacts button:disabled { opacity: .35; cursor: not-allowed; }
        .qp-ovadd { all: unset; box-sizing: border-box; flex: 0 0 112px; min-height: 150px; border: 2px dashed #94a3b8; border-radius: 12px; display: flex; align-items: center; justify-content: center; text-align: center; color: #334155; font-weight: 700; font-size: 0.85rem; cursor: pointer; background: #f8fafc; }
        .qp-ovadd:hover { border-color: #2563eb; color: #1d4ed8; }
        .qp-ovadd:focus-visible { outline: 3px solid #2563eb; }
        .qp-checks { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px; margin-bottom: 16px; display: flex; flex-direction: column; gap: 8px; }
        .qp-warn { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; background: #fffbeb; border: 1px solid #fcd34d; border-radius: 10px; padding: 8px 12px; }
        .qp-warn span { font-size: 0.85rem; color: #78350f; font-weight: 600; }
        .qp-fix { border: 1px solid #b45309; background: #fff; color: #78350f; border-radius: 8px; min-height: 38px; padding: 0 12px; font-size: 0.78rem; font-weight: 700; cursor: pointer; }
        .qp-fix:hover { background: #fef3c7; }
        .qp-draft { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; background: #eff6ff; border: 1px solid #93c5fd; color: #1e3a8a; border-radius: 10px; padding: 10px 14px; margin-bottom: 14px; font-size: 0.88rem; font-weight: 600; }
        .qp-daypills { display: flex; gap: 8px; overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none; padding: 2px 0 12px; margin-bottom: 6px; background: #f8fafc; }
        .qp-daypills::-webkit-scrollbar { display: none; }
        .qp-daypill { position: relative; flex: 0 0 auto; border: 0; border-radius: 999px; min-height: 44px; padding: 0 18px; font-size: 0.9rem; font-weight: 700; cursor: pointer; background: #e2e8f0; color: #1e293b; }
        .qp-daypill.on { background: #1e293b; color: #fff; }
        .qp-daypill .pd { position: absolute; top: 6px; right: 7px; width: 9px; height: 9px; border-radius: 50%; background: #f59e0b; border: 1px solid #fff; }
        .qp-daypill.plus { background: #fff; border: 2px dashed #94a3b8; color: #334155; }
        .qp-active-day { scroll-margin-top: 12px; }
        .qp-set:empty { display: none; }
        .qp-set { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 10px 14px 12px; margin-bottom: 14px; box-shadow: ${UI_THEME.shadows.sm}; }
        .qp-set-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 12px; }
        .qp-set-grid label { display: block; font-size: 0.74rem; font-weight: 700; color: #475569; margin-bottom: 3px; }
        .qp-set-grid .qp-route-select { max-width: 100%; width: 100%; min-height: 38px; padding: 6px 8px; font-size: 0.84rem; }
        @media (max-width: 900px) { .qp-set-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        @media (max-width: 480px) { .qp-set-grid { grid-template-columns: 1fr; } }
        .qp-more { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 14px; box-shadow: ${UI_THEME.shadows.sm}; }
        .qp-more > summary { cursor: pointer; padding: 14px 18px; font-weight: 700; font-size: 0.92rem; color: #1e293b; list-style: none; min-height: 24px; }
        .qp-more > summary::-webkit-details-marker { display: none; }
        .qp-more > summary::after { content: "Show ▾"; float: right; font-weight: 600; font-size: 0.78rem; color: #2563eb; }
        .qp-more[open] > summary::after { content: "Hide ▴"; }
        .qp-more .qp-sub { display: block; font-weight: 500; font-size: 0.76rem; color: #64748b; margin-top: 2px; }
        @media (max-width: 640px) {
          .qp-sticky { position: static; padding: 12px 14px; gap: 8px 16px; }
          .qp-sticky .grow { flex-basis: 100%; order: 5; }
          .qp-gen, .qp-ghost { flex: 1 1 auto; }
          .qp-ovcard { flex-basis: 140px; }
          .qp-daypills { position: sticky; top: 0; z-index: 25; margin: -2px -2px 8px; padding: 8px 2px 10px; border-bottom: 1px solid #e2e8f0; }
        }
        .qp-footer-bar {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 16px;
          margin-top: 20px;
          border-top: 2px solid #e2e8f0;
          padding-top: 16px;
          flex-wrap: wrap;
        }
        .qp-footer-cost {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
        }
        .qp-cost-input {
          padding: 6px 12px;
          font-size: 1.1rem;
          width: 130px;
          border: 1px solid #cbd5e1;
          border-radius: 4px;
          min-height: 40px;
          box-sizing: border-box;
        }
        .qp-hotel-assignments {
          font-size: 0.78rem;
          color: #475569;
          line-height: 1.7;
          max-width: 260px;
          flex: 1 1 200px;
        }
        .qp-save-btn {
          padding: 12px 20px;
          background: #10b981;
          color: #fff;
          border: none;
          border-radius: 5px;
          cursor: pointer;
          font-weight: bold;
          min-height: 48px;
          white-space: nowrap;
          align-self: flex-end;
        }
        @media (max-width: 600px) {
          .qp-footer-bar {
            flex-direction: column;
            align-items: stretch;
          }
          .qp-footer-cost { flex-direction: column; align-items: flex-start; }
          .qp-cost-input { width: 100%; }
          .qp-hotel-assignments { max-width: 100%; }
          .qp-save-btn { width: 100%; text-align: center; }
          .qp-route-select, .qp-hotel-select { max-width: 100%; }
          .qp-time-input { width: 80px; }
        }
        

        /* ===== Compact design layer ===== */
        .qp-wrap { padding: 12px clamp(10px, 3vw, 20px) 20px; font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif; -webkit-font-smoothing: antialiased; }
        .qp-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 14px; margin: 0 0 8px; }
        .qp-head h2 { margin: 0; font-size: 1.15rem; font-weight: 800; letter-spacing: -.01em; color: #0f172a; }
        .qp-head span { font-size: 0.78rem; color: #64748b; }
        .qp-sticky { padding: 7px 12px; border-radius: 10px; margin-bottom: 8px; gap: 4px 18px; background: #111827; }
        .qp-sticky .k { font-size: 0.6rem; }
        .qp-sticky .v { font-size: 0.85rem; }
        .qp-sticky .grow { font-size: 0.74rem; }
        .qp-ghost, .qp-gen { min-height: 32px; font-size: 0.8rem; padding: 0 12px; border-radius: 8px; }
        .qp-gen { background: #1b5666; }
        .qp-badge { font-size: 0.66rem; padding: 1px 7px; margin-left: 6px; }
        .qp-set { padding: 8px 10px; margin-bottom: 8px; border-radius: 10px; }
        .qp-set-grid { gap: 6px 10px; }
        .qp-set-grid label { font-size: 0.66rem; text-transform: uppercase; letter-spacing: .05em; color: #64748b; margin-bottom: 2px; }
        .qp-set-grid .qp-route-select { min-height: 32px; padding: 3px 8px; font-size: 0.82rem; border-radius: 8px; }
        .qp-daysbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px 12px; margin: 4px 0 2px; }
        .qp-daysbar h3 { margin: 0; font-size: 0.95rem; font-weight: 800; color: #0f172a; }
        .qp-daysbar h3 span { font-size: 0.72rem; font-weight: 500; color: #64748b; margin-left: 6px; }
        .qp-chk { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
        .qp-chk-ok { font-size: 0.78rem; font-weight: 700; color: #166534; background: #dcfce7; border-radius: 999px; padding: 3px 10px; }
        .qp-chk-warn { font-size: 0.78rem; font-weight: 800; color: #92400e; background: #fef3c7; border-radius: 999px; padding: 3px 10px; }
        .qp-fix { min-height: 28px; padding: 0 10px; font-size: 0.74rem; border-radius: 999px; border-color: #d6d3d1; color: #44403c; }
        .qp-checks { padding: 8px; margin: 4px 0 6px; gap: 6px; border-radius: 10px; }
        .qp-warn { padding: 4px 8px; border-radius: 8px; }
        .qp-warn span { font-size: 0.8rem; }
        .qp-ov { gap: 8px; padding: 4px 2px 8px; margin-bottom: 4px; }
        .qp-ovcard { flex: 0 0 142px; border-width: 1.5px; border-radius: 10px; }
        .qp-ovcard.on { border-color: #1b5666; box-shadow: 0 0 0 3px #d3e4e7; }
        .qp-ovmain { padding: 8px 10px; gap: 3px; min-height: 84px; }
        .qp-ovdn { font-size: 0.64rem; }
        .qp-ovrt { font-size: 0.82rem; line-height: 1.2; }
        .qp-ovnt { font-size: 0.72rem; color: #475569; }
        .qp-ovhot { font-size: 0.68rem; padding: 2px 6px; max-width: 100%; box-sizing: border-box; }
        .qp-ovacts button { min-height: 30px; font-size: 0.85rem; }
        .qp-ovadd { flex: 0 0 64px; min-height: 0; font-size: 0.78rem; border-radius: 10px; }
        .qp-active-day { padding: 10px 12px 12px; background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 2px rgb(0 0 0 / .04); }
        .qp-daypills { gap: 6px; padding: 0 0 8px; margin-bottom: 4px; background: #fff; }
        .qp-daypill { min-height: 32px; padding: 0 14px; font-size: 0.8rem; }
        .qp-daypill.on { background: #1b5666; }
        .qp-daytitle { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px 12px; margin-bottom: 8px; }
        .qp-daytitle h3 { margin: 0; font-size: 1rem; font-weight: 800; color: #0f172a; }
        .qp-route-select.qp-preset { max-width: 320px; min-height: 32px; padding: 3px 8px; font-size: 0.8rem; border-radius: 8px; }
        .qp-row { display: flex; gap: 10px; align-items: flex-start; padding: 6px 0; border-top: 1px solid #f1f5f9; }
        .qp-rl { flex: 0 0 76px; padding-top: 6px; font-size: 0.74rem; font-weight: 800; color: #334155; text-transform: uppercase; letter-spacing: .04em; }
        .qp-rl small { display: block; font-size: 0.64rem; font-weight: 500; color: #94a3b8; text-transform: none; letter-spacing: 0; line-height: 1.2; }
        .qp-rc { flex: 1 1 auto; min-width: 0; }
        .qp-city-btns { margin-top: 0; gap: 6px; }
        .qp-pair { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr); gap: 8px; align-items: start; margin: 6px 0 2px; padding-top: 8px; border-top: 1px solid #f1f5f9; }
        .qp-pair .qp-hotel-select { max-width: 100%; min-height: 34px; padding: 4px 8px; border-radius: 8px; }
        .qp-ai { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
        .qp-ai input { flex: 1; min-width: 140px; max-width: none; min-height: 34px; padding: 4px 8px; font-size: 0.8rem; border-radius: 8px; }
        .qp-ai button { padding: 0 12px; border-radius: 8px; border: none; background: #1b5666; color: #fff; font-weight: 700; font-size: 0.8rem; min-height: 34px; cursor: pointer; }
        .qp-act { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 8px; }
        .qp-act .qp-activity-row { margin-bottom: 6px; gap: 6px; }
        .qp-time-input, .qp-title-input { min-height: 32px; font-size: 0.82rem; border-radius: 6px; }
        .qp-title-input { font-weight: 700; }
        .qp-time-input { width: 84px; }
        .qp-more { margin-bottom: 8px; border-radius: 10px; }
        .qp-more > summary { display: flex; align-items: center; gap: 8px; padding: 9px 14px; font-size: 0.85rem; }
        .qp-more > summary::after { margin-left: auto; float: none; font-size: 0.72rem; }
        .qp-more .qp-sub { display: inline; margin: 0; font-size: 0.72rem; }
        .qp-footer-bar { margin-top: 10px; padding-top: 10px; align-items: center; }
        .qp-save-btn { background: #1b5666; min-height: 40px; padding: 8px 16px; border-radius: 8px; font-size: 0.88rem; }
        .qp-cost-input { min-height: 36px; font-size: 1rem; border-radius: 8px; }
        .qp-daypill { padding: 0 18px 0 14px; }
        .qp-daypill .pd { top: 50%; right: 6px; transform: translateY(-50%); }
        .qp-pair { grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.4fr); }
        .qp-daypills { flex-wrap: wrap; overflow-x: visible; }
        .qp-daypill { min-height: 32px; }
        @media (max-width: 720px) {
          .qp-set-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .qp-act .qp-activity-row { flex-wrap: nowrap; }
          .qp-act .qp-time-input { width: 78px; }
          .qp-act .qp-title-input { width: auto; min-width: 0; flex: 1; }
        }
        @media (max-width: 720px) {
          .qp-pair { grid-template-columns: 1fr; }
          .qp-row { flex-direction: column; gap: 2px; }
          .qp-rl { flex: none; padding-top: 4px; }
          .qp-rl small { display: inline; margin-left: 6px; }
          .qp-route-select.qp-preset { max-width: 100%; width: 100%; }
        }

        /* ===== Two-column layout, hotel + rooms on the day cards ===== */
        .qp-layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; align-items: start; }
        .qp-hotline { display: flex; align-items: center; gap: 6px 8px; flex-wrap: wrap; width: 100%; }
        .qp-hotline > input { min-height: 34px; padding: 3px 8px; font-size: 0.82rem; border: 1px solid #cbd5e1; border-radius: 8px; box-sizing: border-box; }
        .qp-hotline > select:not(.qp-h-wide) { min-height: 34px; width: auto; max-width: 190px; }
        .qp-hotline .qp-stp span { flex: none; }
        @media (max-width: 720px) {
          .qp-hotline { display: grid; grid-template-columns: 1fr 1fr; }
          .qp-hotline .qp-h-wide { grid-column: 1 / -1; width: 100%; }
          .qp-hotline > select:not(.qp-h-wide) { width: 100%; max-width: none; min-width: 0; text-overflow: ellipsis; }
          .qp-hotline .qp-stp { justify-content: space-between; border: 1px solid #e2e8f0; border-radius: 8px; padding: 2px 4px 2px 8px; }
          .qp-hotline .qp-stp button { width: 30px; height: 30px; }
          .qp-ai > div { gap: 6px !important; }
          .qp-ai input.qp-route-select { min-width: 0 !important; flex: 1 1 120px !important; }
          .qp-daytitle { gap: 4px 8px; }
          .qp-daytitle h3 { font-size: 0.92rem; flex: 1 1 100%; }
          .qp-daytitle .qp-preset { flex: 1 1 0; min-width: 0; }
          .qp-row { padding: 3px 0; }
          .qp-city-btns button { min-height: 28px !important; padding: 2px 10px !important; font-size: 0.76rem !important; }
          .qp-act { padding: 6px; }
          .qp-act textarea { min-height: 44px; }
        }
        .qp-hotline select { min-height: 36px; padding: 3px 8px; font-size: 0.82rem; border: 1px solid #cbd5e1; border-radius: 8px; background: #fff; color: #1e293b; width: 210px; max-width: 100%; box-sizing: border-box; }
        .qp-hotline select.bad { border-color: #fca5a5; background: #fef2f2; color: #991b1b; }
        .qp-hotline .qp-stp button { width: 28px; height: 28px; font-size: 1rem; }
        .qp-dayacts { display: flex; gap: 4px; margin-left: auto; }
        .qp-dayacts button { width: 30px; height: 30px; border: 1px solid #cbd5e1; border-radius: 8px; background: #fff; color: #1e293b; cursor: pointer; font-weight: 700; }
        .qp-dayacts button:disabled { opacity: .35; cursor: not-allowed; }
        .qp-side { position: static !important; max-height: none !important; }
        .qp-side { position: sticky; top: 56px; max-height: calc(100vh - 68px); overflow-y: auto; padding-right: 2px; }
        .qp-main { min-width: 0; }
        .qp-pair.qp-pair1 { grid-template-columns: 1fr; }
        .qp-ov { flex-direction: column; overflow: visible; gap: 8px; padding: 4px 2px 8px; }
        .qp-ovcard { flex: none; width: auto; border-left-width: 4px; }
        .qp-ovcard.ok { border-left-color: #22c55e; }
        .qp-ovcard.warn { border-left-color: #f59e0b; }
        .qp-ovcard.on { border-color: #1b5666; border-left-color: #1b5666; }
        .qp-ovmain { min-height: 0; padding: 7px 10px 4px; gap: 2px; }
        .qp-ovrt { font-size: 0.86rem; }
        .qp-ovok { color: #16a34a; font-weight: 800; font-size: 0.8rem; }
        .qp-ovdrop { margin: 2px 10px 8px; font-size: 0.72rem; font-weight: 700; color: #0369a1; background: #e0f2fe; border-radius: 6px; padding: 3px 7px; align-self: flex-start; }
        .qp-ovhot2 { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; align-items: center; padding: 2px 10px 8px; }
        .qp-ovhot2 select { grid-column: 1 / -1; min-height: 32px; padding: 3px 6px; font-size: 0.8rem; border: 1px solid #cbd5e1; border-radius: 8px; background: #fff; color: #1e293b; width: 100%; box-sizing: border-box; }
        .qp-ovhot2 select.bad { border-color: #fca5a5; background: #fef2f2; color: #991b1b; }
        .qp-ovhot2 label { font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; color: #64748b; display: flex; align-items: center; gap: 6px; }
        .qp-ovhot2 label input { flex: 1; min-width: 0; width: 100%; min-height: 28px; padding: 2px 4px; text-align: center; font-size: 0.85rem; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; background: #f8fafc; }
        .qp-ovadd { flex: none; width: 100%; min-height: 34px; }
        .qp-stp { display: flex; align-items: center; gap: 6px; font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; color: #64748b; }
        .qp-stp span { flex: 1 1 auto; }
        .qp-stp b { min-width: 22px; text-align: center; font-size: 0.95rem; color: #0f172a; }
        .qp-stp button { width: 34px; height: 34px; border: 1px solid #cbd5e1; border-radius: 8px; background: #fff; font-size: 1.1rem; font-weight: 700; color: #1e293b; cursor: pointer; touch-action: manipulation; }
        .qp-stp button:disabled { opacity: .35; cursor: not-allowed; }
        .qp-stp button:active:not(:disabled) { background: #d3e4e7; }
        @media (max-width: 959px) {
          .qp-layout { grid-template-columns: 1fr; }
          .qp-side { position: static; max-height: none; overflow: visible; }
          .qp-ov { flex-direction: column; overflow: visible; }
          .qp-ovcard { flex: none; width: auto; }
          .qp-ovadd { flex: none; width: 100%; min-height: 36px; }
          .qp-footer-bar { position: sticky; bottom: 0; z-index: 30; background: #fff; padding: 8px 10px; margin-top: 8px; box-shadow: 0 -4px 12px rgb(0 0 0 / .08); border-radius: 10px 10px 0 0; flex-direction: row !important; flex-wrap: nowrap; align-items: center !important; gap: 8px; }
          .qp-footer-cost { flex-direction: row !important; align-items: center !important; gap: 6px; flex: 0 0 auto; }
          .qp-footer-cost h3 { font-size: 0.72rem !important; line-height: 1.1; max-width: 62px; }
          .qp-cost-input { width: 92px !important; min-height: 38px; font-size: 0.95rem; }
          .qp-save-btn { flex: 1 1 auto; width: auto !important; min-height: 38px; padding: 6px 8px; font-size: 0.8rem; white-space: normal; align-self: center; }
        }
      
        /* ===== Visual layer: Dal Lake dusk (ink teal, lake blue, saffron) ===== */
        #qp-top { scroll-margin-top: 12px; --ink: #10272e; --lake: #1b5666; --lake-soft: #e8f0f1; --saffron: #c98a14; --line: #dbe5e4; --mute: #5b7479; }
        #qp-top .qp-head h2 { font-family: Georgia, "Iowan Old Style", "Times New Roman", serif; font-weight: 700; font-size: 1.3rem; color: var(--ink); letter-spacing: 0; }
        #qp-top .qp-head span { color: var(--mute); }
        #qp-top .qp-sticky { background: linear-gradient(120deg, #10272e 0%, #17414d 100%); border-bottom: 3px solid var(--saffron); border-radius: 12px; box-shadow: 0 10px 24px -14px rgb(16 39 46 / .7); padding: 10px 16px; }
        #qp-top .qp-sticky .k { color: #9fc0c6; letter-spacing: .05em; }
        #qp-top .qp-sticky .v { font-family: Georgia, "Iowan Old Style", serif; font-weight: 700; font-size: 1.02rem; }
        #qp-top .qp-set, #qp-top .qp-more { border-color: var(--line); border-radius: 14px; box-shadow: 0 12px 28px -24px rgb(16 39 46 / .5); }
        #qp-top .qp-fix { border-color: #c9dde0; color: var(--lake); }
        #qp-top .qp-chk-warn { background: #fff3d6; color: #8a5a00; }
        #qp-top .qp-save-btn { background: var(--ink); border: 0; border-bottom: 3px solid var(--saffron); }

        /* Day editor: one calm sheet */
        #qp-top .qp-active-day { background: #fff; border: 1px solid var(--line); border-radius: 16px; padding: 14px 18px 18px; box-shadow: 0 1px 0 rgb(16 39 46 / .04), 0 18px 40px -30px rgb(16 39 46 / .55); }
        #qp-top .qp-daypills { background: transparent; gap: 4px; padding: 0 0 10px; margin-bottom: 12px; border-bottom: 1px solid var(--line); }
        #qp-top .qp-daypill { background: transparent; border: 0; border-radius: 999px; color: var(--mute); font-weight: 600; min-height: 32px; padding: 0 22px 0 14px; transition: background .15s, color .15s; }
        #qp-top .qp-daypill:hover:not(.on) { background: var(--lake-soft); color: var(--ink); }
        #qp-top .qp-daypill.on { background: var(--ink); color: #fff; box-shadow: none; }
        #qp-top .qp-daypill .pd { background: var(--saffron); }
        #qp-top .qp-daypill.plus { border: 1px dashed #9db9be; color: var(--lake); background: transparent; }
        #qp-top .qp-daytitle { margin-bottom: 10px; gap: 8px 12px; }
        #qp-top .qp-daytitle h3 { font-family: Georgia, "Iowan Old Style", serif; font-size: 1.3rem; line-height: 1.2; font-weight: 700; color: var(--ink); }
        #qp-top .qp-dayacts { gap: 2px; background: var(--lake-soft); border-radius: 10px; padding: 2px; }
        #qp-top .qp-dayacts button { border: 0; background: transparent; width: 30px; height: 28px; border-radius: 8px; color: var(--ink); }
        #qp-top .qp-dayacts button:hover:not(:disabled) { background: #fff; }
        #qp-top .qp-daytitle .qp-preset { border: 1px solid var(--line); border-radius: 10px; background: #fff; color: var(--mute); max-width: 260px; min-height: 34px; font-size: .8rem; }

        /* Route as a journey: a thin rail with a stop per row */
        #qp-top #day-route-select { margin: 4px 0 12px; }
        #qp-top .qp-row { position: relative; border-top: 0; padding: 5px 0 5px 24px; gap: 12px; align-items: flex-start; }
        #qp-top .qp-row::before { content: ""; position: absolute; left: 0; top: 13px; width: 10px; height: 10px; border-radius: 50%; border: 2px solid var(--lake); background: #fff; box-sizing: border-box; }
        #qp-top .qp-row:has(+ .qp-row)::after { content: ""; position: absolute; left: 4px; top: 23px; bottom: -13px; width: 2px; background: #cfe0e3; }
        #qp-top .qp-rl { flex: 0 0 52px; padding-top: 5px; font-size: .84rem; font-weight: 700; color: var(--ink); text-transform: none; letter-spacing: 0; white-space: nowrap; }
        #qp-top .qp-rl small { font-size: .68rem; font-weight: 500; color: var(--mute); }
        #qp-top .qp-city-btns { gap: 5px; }
        #qp-top .qp-city-btns button:hover:not(:disabled) { filter: brightness(.96); }

        /* Stay + AI toolbar */
        #qp-top .qp-ai > div { gap: 8px; align-items: stretch; }
        #qp-top .qp-hotline { width: auto; flex: 0 1 auto; background: var(--lake-soft); border: 0; border-radius: 12px; padding: 6px 8px; gap: 8px; }
        #qp-top .qp-hotline select.qp-h-wide { width: 230px; border-color: transparent; background: #fff; }
        #qp-top .qp-hotline select.bad { border: 1px solid #e0a45a; background: #fff6e8; color: #8a4b00; }
        #qp-top .qp-stp { background: #fff; border-radius: 9px; padding: 2px 3px 2px 9px; gap: 4px; color: var(--mute); }
        #qp-top .qp-stp button { border: 0; background: var(--lake-soft); width: 26px; height: 26px; border-radius: 7px; }
        #qp-top .qp-stp b { min-width: 20px; }
        #qp-top .qp-nohotel { font-size: .82rem; color: var(--mute); padding: 0 6px; align-self: center; }
        #qp-top .qp-hotline:has(.qp-nohotel) { background: transparent; padding: 0; }
        #qp-top .qp-ai input.qp-route-select { border: 1px solid var(--line); background: #fff; border-radius: 10px; }
        #qp-top .qp-ai > div > button { background: var(--saffron); color: #1b1200; border-radius: 10px; min-height: 40px; }

        /* Activities */
        #qp-top .qp-act { background: #fff; border: 1px solid var(--line); border-left: 3px solid var(--saffron); border-radius: 12px; padding: 10px 12px; }
        #qp-top .qp-act input, #qp-top .qp-act textarea { background: #f6f9f9; border-color: transparent; border-radius: 9px; }
        #qp-top .qp-act input:hover, #qp-top .qp-act textarea:hover { border-color: #c9dde0; }
        #qp-top .qp-act .qp-time-input { color: var(--lake); font-weight: 600; }
        #qp-top .qp-act .qp-title-input { font-weight: 700; color: var(--ink); }

        #qp-top select:focus-visible, #qp-top input:focus-visible, #qp-top textarea:focus-visible, #qp-top button:focus-visible { outline: 2px solid var(--lake); outline-offset: 1px; }
        @media (max-width: 720px) {
          #qp-top .qp-active-day { padding: 10px 12px 14px; border-radius: 14px; }
          #qp-top .qp-daytitle h3 { font-size: 1.1rem; }
          #qp-top .qp-rl { flex-basis: auto; }
          #qp-top .qp-row { flex-direction: column; gap: 0; padding-left: 20px; }
          #qp-top .qp-row::before { top: 9px; }
          #qp-top .qp-row:has(+ .qp-row)::after { top: 19px; }
          #qp-top .qp-hotline { display: grid; grid-template-columns: 1fr 1fr; width: 100%; }
          #qp-top .qp-hotline select.qp-h-wide { width: 100%; }
        }
        @media (prefers-reduced-motion: reduce) { #qp-top * { transition: none !important; } }
`}</style>

      <div className="qp-wrap" id="qp-top">
        {/* 1. Header */}
        <div className="qp-head">
          <h2>Build the itinerary</h2>
          <span>① route &amp; hotel for each day &nbsp;→&nbsp; ② rooms &nbsp;→&nbsp; ③ Generate PDF</span>
        </div>

        {/* 2. Sticky summary bar */}
        <div className="qp-sticky">
          <div><div className="k">Client</div><div className="v">{quote?.meta_summary?.client_name || "N/A"}</div></div>
          <div><div className="k">Trip</div><div className="v">{timeline.length} days · {quote?.meta_summary?.budget_tier || "N/A"} · {vehicleType || "N/A"} · {mealPlan}</div></div>
          <div><div className="k">Estimated total</div><div className="v">{fmtINR(Number(editableCost) || 0)}</div></div>
          <div className="grow" aria-live="polite">{saveState === "saving" ? "Saving…" : "All changes saved"}</div>
          <button type="button" className="qp-ghost" onClick={undo} disabled={!canUndo} aria-label="Undo last change">Undo</button>
          <button type="button" className="qp-ghost" onClick={redo} disabled={!canRedo} aria-label="Redo">Redo</button>
          <button type="button" className="qp-gen" onClick={generateChecked} disabled={pdfBusy}>
            {pdfBusy ? "Generating…" : "Generate PDF"}
            {!pdfBusy && <span className={"qp-badge" + (issues.length ? "" : " ok")}>{issues.length ? `${issues.length} ${issues.length === 1 ? "issue" : "issues"}` : "Ready"}</span>}
          </button>
        </div>

        {draftOffer && (
          <div className="qp-draft">
            <span>An unsaved draft from {new Date(draftOffer.at || Date.now()).toLocaleString()} was found on this device.</span>
            <span style={{ display: "flex", gap: "8px" }}>
              <button type="button" className="qp-fix" style={{ borderColor: "#1d4ed8", color: "#1e3a8a" }} onClick={restoreDraft}>Restore draft</button>
              <button type="button" className="qp-fix" style={{ borderColor: "#64748b", color: "#334155" }} onClick={discardDraft}>Discard</button>
            </span>
          </div>
        )}

        {/* Trip settings: vehicle, meal plan, start and end point in one compact row */}
        <div className="qp-set">
          {[["start", "Start", startPoint, changeStart], ["end", "End", endPoint, changeEnd]].map(([key, label, val, setter]) => {
            const showFind = !isSrinagarPoint(val) && val.trim().length >= 3;
            if (!showFind) return null;
            const info = key === "start" ? startInfo : endInfo;
            const small = { width: "78px", padding: "4px 6px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "0.8rem", boxSizing: "border-box" };
            return (
              <div key={key} style={{ marginTop: "8px" }}>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                  <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "#334155" }}>{label} point: {val}</span>
                  {showFind && (
                    <button type="button" onClick={() => locatePoint(key)} disabled={!!locBusy}
                      style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid #c4b5fd", background: "#f5f3ff", color: "#1b5666", fontWeight: "bold", cursor: locBusy ? "wait" : "pointer", fontSize: "0.8rem" }}>
                      {locBusy === key ? "Looking up…" : "📍 Find location & distance (AI)"}
                    </button>
                  )}
                </div>
                {info && (
                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px", alignItems: "center", fontSize: "0.72rem", color: "#64748b" }}>
                    <span>Lat</span><input style={small} type="number" step="0.0001" value={info.lat ?? ""} onChange={(e) => editInfo(key, "lat", e.target.value)} />
                    <span>Lon</span><input style={small} type="number" step="0.0001" value={info.lon ?? ""} onChange={(e) => editInfo(key, "lon", e.target.value)} />
                    <span>km by road</span><input style={small} type="number" value={info.km ?? ""} onChange={(e) => editInfo(key, "km", e.target.value)} />
                    <span>hrs</span><input style={{ ...small, width: "60px" }} type="number" step="0.5" value={info.hours ?? ""} onChange={(e) => editInfo(key, "hours", e.target.value)} />
                  </div>
                )}
                {locMsg[key] && <div style={{ fontSize: "0.72rem", color: info ? "#7e6a9b" : "#b91c1c", marginTop: "4px" }}>{locMsg[key]}</div>}
              </div>
            );
          })}
        </div>

        <div className="qp-layout">
        <div className="qp-side">
        {/* 3. Days strip with the checks summary on the same line */}
        <div className="qp-daysbar">
          <h3>Your days <span>tap a day to edit</span></h3>
          <div className="qp-chk">
            {issues.length === 0
              ? <span className="qp-chk-ok">✓ All set, ready for the PDF</span>
              : <>
                  <span className="qp-chk-warn">⚠ {issues.length} to finish</span>
                  {missingHotelDays.length > 0 && (
                    <button type="button" className="qp-fix" onClick={fixAllHotels}>Pick hotels ({missingHotelDays.length})</button>
                  )}
                  <button type="button" className="qp-fix" onClick={() => setShowChecks((v) => !v)}>{showChecks ? "Hide" : "Details"}</button>
                </>}
          </div>
        </div>
        {issues.length > 0 && showChecks && (
          <div className="qp-checks">
            {issues.map((w, k) => (
              <div key={k} className="qp-warn"><span>{w.text}</span><button type="button" className="qp-fix" onClick={w.fix}>{w.btn}</button></div>
            ))}
          </div>
        )}

        </div>
        <div className="qp-main">
        {/* 4. Active day editor */}
        {timeline[activeDay] && (
          <div className="qp-active-day" id="qp-editor">
            <div className="qp-daypills" role="tablist" aria-label="Days">
              {timeline.map((d, i) => (
                <button key={i} type="button" role="tab" aria-selected={i === activeDay} className={"qp-daypill" + (i === activeDay ? " on" : "")} onClick={() => setActiveDay(i)}>
                  Day {i + 1}{warnDays.has(i) && <span className="pd" title="Needs attention" />}
                </button>
              ))}
              <button type="button" className="qp-daypill plus" onClick={addDay} aria-label="Add a day">+ Day</button>
            </div>
            <div className="qp-daytitle">
              <h3>Day {timeline[activeDay].day}: {timeline[activeDay].title || timeline[activeDay].date}</h3>
              <div className="qp-dayacts">
                <button type="button" onClick={() => moveDay(activeDay, -1)} disabled={activeDay === 0} aria-label="Move day earlier" title="Move earlier">&#8249;</button>
                <button type="button" onClick={() => moveDay(activeDay, 1)} disabled={activeDay === timeline.length - 1} aria-label="Move day later" title="Move later">&#8250;</button>
                <button type="button" onClick={() => copyDay(activeDay)} aria-label="Duplicate day" title="Duplicate this day">⧉</button>
                <button type="button" onClick={() => deleteDay(activeDay)} disabled={timeline.length <= 1} aria-label="Delete day" title="Remove this day">✕</button>
              </div>
              <select
                className="qp-route-select qp-preset"
                value={TRANSIT_OPTIONS.includes(timeline[activeDay].transit_route) ? timeline[activeDay].transit_route : ""}
                onChange={(e) => { const route = e.target.value; if (route) applyRoute(route); }}
              >
                <option value="">{timeline[activeDay].transit_route && !TRANSIT_OPTIONS.includes(timeline[activeDay].transit_route) ? `Custom route (built from the steps)` : "⚡ Quick start: pick a ready-made day"}</option>
                {TRANSIT_OPTIONS.map((route, i) => <option key={i} value={route}>{routeLabel(route, startPoint, endPoint)}</option>)}
              </select>
            </div>

            {/* Route picker: Starting from -> Going to -> Overnight */}
            {(() => {
              const day = timeline[activeDay];
              const parsed = parseRoute(day.transit_route);
              const draft = pickDraft[activeDay] || {};
              const prevNight = activeDay > 0 ? (timeline[activeDay - 1]?.overnight_stay || "") : "";
              const autoFrom = activeDay === 0 ? "Airport" : (isFromPlace(prevNight) ? prevNight : "Srinagar");
              const from  = draft.from  ?? parsed?.from  ?? autoFrom;
              const to    = draft.to    ?? parsed?.to    ?? "";
              const isDep = to === "Departure";
              const night = isDep ? "" : (draft.night ?? parsed?.night ?? "");
              const customRoute = !parsed && !!day.transit_route;

              const pick = (patch) => {
                const next = { from, to, night, ...patch };
                // Day 1 starts where the guests are collected: a real place (e.g. Pathankot) becomes the tour
                // start point, so the PDF cover, journey line and map show it. "Airport" keeps the start point as set.
                if (activeDay === 0 && patch.from !== undefined) {
                  const wantStart = patch.from === "Airport" ? DEFAULT_POINT : patch.from;
                  if (wantStart !== startPoint) changeStart(wantStart);
                }
                if (patch.to !== undefined && patch.night === undefined) next.night = patch.to === "Departure" ? "" : defaultNightFor(patch.to, next.from);
                if (next.to === "Departure" || (next.to && next.night)) {
                  applyRoute(routeTitle(next.from, next.to, next.night));
                } else {
                  setPickDraft(prev => ({ ...prev, [activeDay]: next }));
                }
              };
              const pickNight = (city) => {
                if (customRoute || (!to && day.transit_route)) {
                  // Hand-picked preset (e.g. "Pahalgam: Local Sightseeing"): only change where they sleep.
                  setTimeline(prev => prev.map((d, i) => i === activeDay ? { ...d, overnight_stay: city } : d));
                  setHotelSelections(prev => ({ ...prev, [activeDay]: null }));
                } else pick({ night: city });
              };

              const chipStyle = (on, disabled) => ({
                padding: "3px 12px", borderRadius: "999px", minHeight: "28px", fontSize: "0.8rem", fontWeight: 600,
                border: on ? "1px solid #1b5666" : "1px solid transparent", backgroundColor: on ? "#1b5666" : "#edf2f2",
                color: on ? "#fff" : "#1f3f47", cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.4 : 1, transition: "background-color .12s, color .12s",
              });
              const row = (step, label, hint, options, value, onPick, disabled) => (
                <div className="qp-row">
                  <label className="qp-rl">{label}{hint && <small>{hint}</small>}</label>
                  <div className="qp-rc">
                    <div className="qp-city-btns">
                      {options.map((o) => {
                        const custom = customNames().includes(o);
                        return (
                          <span key={o} style={{ display: "inline-flex", alignItems: "center", gap: "2px" }}>
                            <button type="button" disabled={disabled} onClick={() => onPick(o)} style={{ ...chipStyle(value === o, disabled), ...(custom && !disabled ? { borderTopRightRadius: 0, borderBottomRightRadius: 0 } : {}) }}>{o}</button>
                            {custom && !disabled && (
                              <button type="button" title={`Remove ${o} from the lists`} aria-label={`Remove ${o}`} onClick={() => removeCustomPlace(o)}
                                style={{ ...chipStyle(false, false), padding: "4px 8px", marginLeft: "-3px", borderTopLeftRadius: 0, borderBottomLeftRadius: 0, color: "#b91c1c", borderColor: "#fecaca" }}>✕</button>
                            )}
                          </span>
                        );
                      })}
                      {!disabled && addOpen !== step && (
                        <button type="button" onClick={() => { setAddOpen(step); setAddText(""); setAddErr(""); }} style={{ ...chipStyle(false, false), borderStyle: "dashed", color: "#1b5666", borderColor: "#8fb3ba", backgroundColor: "transparent" }}>+ Place</button>
                      )}
                    </div>
                    {!disabled && addOpen === step && (
                      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center", marginTop: "6px" }}>
                        <input
                          autoFocus
                          className="qp-route-select"
                          style={{ maxWidth: "240px", minHeight: "32px" }}
                          placeholder="Place name, e.g. Sopore"
                          maxLength={40}
                          value={addText}
                          disabled={addBusy}
                          onChange={(e) => setAddText(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") { e.preventDefault(); addCustomPlace(addText, onPick); }
                            if (e.key === "Escape") setAddOpen(null);
                          }}
                        />
                        <button type="button" disabled={addBusy || !addText.trim()} onClick={() => addCustomPlace(addText, onPick)} style={{ ...chipStyle(true, false) }}>{addBusy ? "Locating…" : "Add"}</button>
                        <button type="button" disabled={addBusy} onClick={() => setAddOpen(null)} style={chipStyle(false, false)}>Cancel</button>
                        {addErr && <div style={{ width: "100%", color: "#b91c1c", fontSize: "0.78rem" }}>{addErr}</div>}
                      </div>
                    )}
                  </div>
                </div>
              );

              return (
                <div id="day-route-select">
                  {row(1, "From", activeDay > 0 && !draft.from && !parsed && prevNight ? `Day ${activeDay} night` : (parsed && activeDay > 0 && from !== autoFrom ? `Day ${activeDay} ended in ${prevNight || "?"}` : ""), fromOptions(), from, (o) => pick({ from: o }))}
                  {row(2, "To", "", toOptions(), to, (o) => pick({ to: o }))}
                  {row(3, "Stay", isDep ? "not needed" : "", nightOptions(), night || (customRoute ? (day.overnight_stay || "") : ""), pickNight, isDep)}
                  {(isDep || day.transit_route === DROP_ROUTE) && row(4, "Drop at", "", [...POINT_PRESETS, ...fromOptions().filter((o) => o !== "Airport" && o !== "Srinagar")], endPoint || DEFAULT_POINT, (o) => changeEnd(o))}
                  {addNote && <div style={{ fontSize: "0.8rem", color: "#92400e", background: "#fffbeb", border: "1px solid #fde68a", borderRadius: "8px", padding: "8px 10px", marginBottom: "10px" }}>{addNote}</div>}
                  {customRoute && <div style={{ fontSize: "0.78rem", color: "#64748b", marginBottom: "10px" }}>Using “{day.transit_route}”. Pick From / To to replace it.</div>}
                </div>
              );
            })()}

            <div className="qp-pair qp-pair1">
            {/* AI writer */}
            <div className="qp-ai">
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                {(() => {
                  const d = timeline[activeDay];
                  const i = activeDay;
                  const dep = isDepDay(d);
                  const list = dep ? [] : (HOTEL_KB[getHotelGroup(d.overnight_stay)] || []);
                  return (
                    <div className="qp-hotline">
                      {dep ? <span className="qp-nohotel">Departure day, no hotel needed</span> : (
                        <>
                          <select className={"qp-h-wide" + (hotelSelections[i] ? "" : " bad")} aria-label={`Hotel for day ${i + 1}`} value={hotelSelections[i] || ""}
                            onChange={(e) => setHotelSelections((prev) => ({ ...prev, [i]: e.target.value }))}>
                            <option value="">{list.length ? "Choose hotel…" : `No hotels in ${d.overnight_stay || "this place"}`}</option>
                            {list.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
                          </select>
                          {[["rooms", "Rooms", 1, 1, 20], ["eb", "EB", 0, 0, 20]].map(([f, lbl, def, min, max]) => {
                            const v = Math.max(min, Math.min(max, Number(d[f] ?? def) || def));
                            return (
                              <div key={f} className="qp-stp">
                                <span>{lbl}</span>
                                <button type="button" aria-label={`Fewer ${lbl}`} disabled={v <= min} onClick={() => setRoomField(i, f, v - 1)}>−</button>
                                <b>{v}</b>
                                <button type="button" aria-label={`More ${lbl}`} disabled={v >= max} onClick={() => setRoomField(i, f, v + 1)}>+</button>
                              </div>
                            );
                          })}
                        </>
                      )}
                    </div>
                  );
                })()}
                <input
                  className="qp-route-select"
                  style={{ flex: 1, minWidth: "160px", maxWidth: "none" }}
                  placeholder="AI hints: honeymoon, relaxed pace…"
                  maxLength={300}
                  value={aiHints}
                  onChange={(e) => setAiHints(e.target.value)}
                />
                <button
                  type="button"
                  onClick={aiRewriteDay}
                  disabled={!!aiBusy}
                  style={{ padding: "8px 14px", borderRadius: "6px", border: "none", background: "#b4690a", color: "#fff", fontWeight: "bold", cursor: aiBusy ? "wait" : "pointer", minHeight: "38px", opacity: aiBusy ? 0.7 : 1 }}
                >
                  {aiBusy === "day" ? "Writing…" : "✨ Rewrite day"}
                </button>
              </div>
              {aiError && <div style={{ color: "#b91c1c", fontSize: "0.8rem", marginTop: "6px" }}>{aiError}</div>}
            </div>

            </div>

            {/* Activity list */}
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "10px" }}>
              {timeline[activeDay].schedule.map((slot, actIdx) => (
                <div key={actIdx} className="qp-act">
                  <div className="qp-activity-row">
                    <input
                      type="text"
                      value={slot.time_slot}
                      onChange={(e) => { const t = [...timeline]; t[activeDay].schedule[actIdx].time_slot = e.target.value; setTimeline(t); }}
                      className="qp-time-input"
                    />
                    <input
                      type="text"
                      value={slot.activity_title}
                      onChange={(e) => { const t = [...timeline]; t[activeDay].schedule[actIdx].activity_title = e.target.value; setTimeline(t); }}
                      className="qp-title-input"
                    />
                    <button
                      type="button"
                      onClick={() => aiWriteActivity(actIdx)}
                      disabled={!!aiBusy}
                      title="Write this description with AI"
                      style={{ padding: "4px 10px", borderRadius: "6px", border: "1px solid #b9d0d4", background: "#e4eef0", color: "#1b5666", fontWeight: "bold", fontSize: "0.8rem", cursor: aiBusy ? "wait" : "pointer", minHeight: "32px", flexShrink: 0, opacity: aiBusy ? 0.7 : 1 }}
                    >
                      {aiBusy === "act-" + actIdx ? "Writing…" : "✨ Write"}
                    </button>
                  </div>
                  <textarea
                    value={slot.description}
                    onChange={(e) => handleDescriptionChange(activeDay, actIdx, e.target.value)}
                    style={{ width: "100%", padding: "6px 8px", border: "1px solid #e2e8f0", borderRadius: "6px", boxSizing: "border-box", resize: "vertical", fontSize: "0.85rem", fontFamily: "inherit" }}
                    rows={2}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        </div>
        </div>

        {/* 6. Hotel photo manager (rarely needed) */}
        <details className="qp-more">
          <summary><b>🏨 Hotels &amp; photos</b> <span className="qp-sub">add a hotel or its photos</span></summary>
          <div style={{ padding: "4px 10px 12px" }}>
            <HotelImageManager />
          </div>
        </details>

        {/* 7. Footer / PDF export */}
        <div className="qp-footer-bar">
          <div className="qp-footer-cost">
            <h3 style={{ margin: 0, fontSize: "1rem" }}>Total Est. Cost (₹):</h3>
            <input
              type="number"
              value={editableCost}
              onChange={(e) => setEditableCost(e.target.value)}
              className="qp-cost-input"
            />
          </div>

          <button
            className="qp-save-btn"
            onClick={generateChecked}
            disabled={pdfBusy}
          >
            {pdfBusy ? "Generating…" : "💾 Lock Changes & Generate PDF"}
          </button>
        </div>
      </div>
    </>
  );
}
