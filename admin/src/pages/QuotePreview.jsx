import React, { useState, useEffect, useRef } from "react";
import { apiFetch } from "../api.js";
import { Icon, Sheet, Stepper, PickRow } from "../components/ui.jsx";

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

// Room type printed on the quote's "Where you'll stay" cards (a day's choice carries to later days, like rooms / EB).
const ROOM_TYPES = ["Deluxe Room", "Super Deluxe Room", "Premium Room", "Executive Room", "Family Room", "Suite", "Cottage", "Houseboat Cabin"];
const DEFAULT_ROOM_TYPE = "Deluxe Room";

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
export default function QuotePreview({ quote, trip, step = "days", onStep = () => {} }) {
  const [timeline,        setTimeline]        = useState(quote?.itinerary_timeline || []);
  const [activeDay,       setActiveDay]       = useState(0);
  const [editableCost,    setEditableCost]    = useState(quote?.financial_summary?.total_payable_inr || 38500);
  const [showPerPerson,   setShowPerPerson]   = useState(false);   // per-person price on the PDF cover is opt-in
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
  // Older saved drafts used one "union_cab" key; it meant Pahalgam and Gulmarg.
  const legacyExtras = (ex) => (ex || []).flatMap((k) => (k === "union_cab" ? ["union_cab_pahalgam", "union_cab_gulmarg"] : [k]));
  const [includedExtras, setIncludedExtras] = useState(legacyExtras(quote?.included_extras));   // union cabs per place / gondola phases counted in the package
  const toggleExtra = (k) => setIncludedExtras((a) => (a.includes(k) ? a.filter((x) => x !== k) : [...a, k]));
  // Own places for "Union cab · Other", and own inclusion lines (each with its own on/off switch).
  const [cabOtherPlaces, setCabOtherPlaces] = useState(Array.isArray(quote?.cab_other_places) ? quote.cab_other_places : []);
  const [customIncl, setCustomIncl] = useState(Array.isArray(quote?.custom_inclusions) ? quote.custom_inclusions.map((t) => ({ t, on: true })) : []);
  const [otherIn, setOtherIn] = useState("");
  const [inclIn, setInclIn] = useState("");
  const addOtherPlace = () => {
    const v = otherIn.trim();
    if (!v) return;
    setCabOtherPlaces((a) => (a.some((x) => x.toLowerCase() === v.toLowerCase()) ? a : [...a, v].slice(0, 6)));
    setOtherIn("");
  };
  const addCustomIncl = () => {
    const v = inclIn.trim();
    if (!v) return;
    setCustomIncl((a) => (a.length >= 8 ? a : [...a, { t: v, on: true }]));
    setInclIn("");
  };
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
      localStorage.setItem(draftKey, JSON.stringify({ ...snap, startPoint, endPoint, editableCost, showPerPerson, includedExtras, cabOtherPlaces, customIncl, vehicleType, mealPlan, at: Date.now() }));
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
    if (typeof d.showPerPerson === "boolean") setShowPerPerson(d.showPerPerson);
    if (Array.isArray(d.includedExtras)) setIncludedExtras(legacyExtras(d.includedExtras));
    if (Array.isArray(d.cabOtherPlaces)) setCabOtherPlaces(d.cabOtherPlaces);
    if (Array.isArray(d.customIncl)) setCustomIncl(d.customIncl);
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
  const coupleOn = !!trip?.couple && Number(quote?.meta_summary?.adults || quote?.adults || 2) === 2;
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
                    show_per_person: showPerPerson,
                    included_extras: [...includedExtras, ...(coupleOn ? (trip?.coupleExtras || []) : [])],
                    cab_other_places: cabOtherPlaces,
                    custom_inclusions: customIncl.filter((c) => c.on).map((c) => c.t),
                    couple: coupleOn,
                    vehicle_type: vehicleType,
                    meal_plan: mealPlan,
                    return_pdf: true,
                    timeline: timeline.map((d) => (isDepDay(d) || d.room_type ? d : { ...d, room_type: DEFAULT_ROOM_TYPE })),
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


  // ══ Mobile builder UI (Days step + Review step) ═══════════════════════════
  // The Trip step is the LeadForm; App.jsx decides which step shows. All state and
  // logic above is unchanged: this part only draws it as tap-friendly screens.
  const [sheet, setSheet]     = useState(null);   // { type, step? }  one bottom sheet at a time
  const [openAct, setOpenAct] = useState(0);      // expanded activity (-1 = none)
  const touch = useRef(null);
  const chipsRef = useRef(null);
  const [hotelQ, setHotelQ] = useState("");
  useEffect(() => { setOpenAct(0); }, [activeDay, quote]);

  // Changing day always restarts the screen at the top of that day: page scrolled to the top,
  // the day strip centred on the new day, and any open sheet closed.
  const goDay = (n) => {
    if (n < 0 || n >= timeline.length) return;
    setSheet(null);
    setActiveDay(n);
  };
  useEffect(() => {
    if (step === "review") return;
    const up = () => {
      window.scrollTo({ top: 0, left: 0 });
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
      const on = chipsRef.current?.querySelector(".sv-chip.on");
      if (on && on.scrollIntoView) on.scrollIntoView({ inline: "center", block: "nearest" });
    };
    up();
    const r = requestAnimationFrame(up);          // again after the new day has drawn
    const t = setTimeout(up, 120);                // and once more in case the keyboard or layout moved things
    return () => { cancelAnimationFrame(r); clearTimeout(t); };
  }, [activeDay, step]);


  const closeSheet = () => { setSheet(null); setHotelQ(""); setAddText(""); setAddErr(""); setAddOpen(null); };
  const goStep = (s) => { onStep(s); window.scrollTo({ top: 0, behavior: "smooth" }); };

  const day = timeline[activeDay];
  if (!day) return <div className="sv-empty">No days yet. Go back to Trip and build the itinerary.</div>;

  // Route picker state (From / To / Stay), same rules as before.
  const dep       = isDepDay(day);
  const parsed    = parseRoute(day.transit_route);
  const draft     = pickDraft[activeDay] || {};
  const prevNight = activeDay > 0 ? (timeline[activeDay - 1]?.overnight_stay || "") : "";
  const autoFrom  = activeDay === 0 ? "Airport" : (isFromPlace(prevNight) ? prevNight : "Srinagar");
  const rFrom     = draft.from ?? parsed?.from ?? autoFrom;
  const rTo       = draft.to   ?? parsed?.to   ?? "";
  const rIsDep    = rTo === "Departure";
  const rNight    = rIsDep ? "" : (draft.night ?? parsed?.night ?? "");
  const customRoute = !parsed && !!day.transit_route;

  const pick = (patch) => {
    const next = { from: rFrom, to: rTo, night: rNight, ...patch };
    // Day 1 starts where guests are collected, so a real place becomes the tour start point.
    if (activeDay === 0 && patch.from !== undefined) {
      const wantStart = patch.from === "Airport" ? DEFAULT_POINT : patch.from;
      if (wantStart !== startPoint) changeStart(wantStart);
    }
    if (patch.to !== undefined && patch.night === undefined) next.night = patch.to === "Departure" ? "" : defaultNightFor(patch.to, next.from);
    if (next.to === "Departure" || (next.to && next.night)) applyRoute(routeTitle(next.from, next.to, next.night));
    else setPickDraft((prev) => ({ ...prev, [activeDay]: next }));
  };
  const pickNight = (city) => {
    if (customRoute || (!rTo && day.transit_route)) {
      setDayField(activeDay, "overnight_stay", city);
      setHotelSelections((prev) => ({ ...prev, [activeDay]: null }));
    } else pick({ night: city });
  };
  const choose = (step, value) => {
    if (step === "from") pick({ from: value });
    else if (step === "to") pick({ to: value });
    else pickNight(value);
    closeSheet();
  };

  const stayValue  = dep ? "" : (rNight || day.overnight_stay || "");
  const heading    = day.transit_route ? shortRoute(day).replace(" to ", " → ") : (rTo ? `${rFrom} → ${rTo}` : "Choose where this day goes");
  const hotelList  = dep ? [] : (HOTEL_KB[getHotelGroup(day.overnight_stay)] || []);
  const hotelName  = hotelSelections[activeDay] ? ALL_HOTELS_FLAT[hotelSelections[activeDay]]?.name : "";
  const dayIssues  = issues.filter((q) => q.day === activeDay);
  const rooms      = Math.max(1, Math.min(20, Number(day.rooms ?? 1) || 1));
  const ebs        = Math.max(0, Math.min(20, Number(day.eb ?? 0) || 0));

  // Activities (immutable updates)
  const setAct = (idx, patch) => setTimeline((prev) => prev.map((d, i) => i !== activeDay ? d : {
    ...d, schedule: d.schedule.map((x, j) => j === idx ? { ...x, ...patch } : x),
  }));
  const moveAct = (idx, dir) => setTimeline((prev) => prev.map((d, i) => {
    if (i !== activeDay) return d;
    const s = [...d.schedule], j = idx + dir;
    if (j < 0 || j >= s.length) return d;
    [s[idx], s[j]] = [s[j], s[idx]];
    return { ...d, schedule: s };
  }));
  const delAct = (idx) => { setTimeline((prev) => prev.map((d, i) => i !== activeDay ? d : { ...d, schedule: d.schedule.filter((_, j) => j !== idx) })); setOpenAct(-1); };
  const addAct = () => {
    setTimeline((prev) => prev.map((d, i) => i !== activeDay ? d : { ...d, schedule: [...d.schedule, { time_slot: "***", activity_title: "New activity", description: "" }] }));
    setOpenAct(day.schedule.length);
  };

  // Swipe left / right on the day to change day.
  const onTouchStart = (e) => { const t = e.touches[0]; touch.current = { x: t.clientX, y: t.clientY }; };
  const onTouchEnd = (e) => {
    const s = touch.current; touch.current = null;
    if (!s || e.target.closest("input, textarea, select, .sv-chips")) return;
    const t = e.changedTouches[0], dx = t.clientX - s.x, dy = t.clientY - s.y;
    if (Math.abs(dx) > 70 && Math.abs(dy) < 50) {
      const n = activeDay + (dx < 0 ? 1 : -1);
      goDay(n);
    }
  };

  const runFix = (q) => {
    q.fix();
    if (q.btn === "Open day") onStep("days");
  };

  const optionList = (step) => step === "from" ? fromOptions() : step === "to" ? toOptions() : nightOptions();
  const optionValue = (step) => step === "from" ? rFrom : step === "to" ? rTo : stayValue;
  const sheetTitle = { from: "Starting from", to: "Going to", stay: "Stay overnight in" };
  const endOptions = [...POINT_PRESETS, ...fromOptions().filter((o) => o !== "Airport" && o !== "Srinagar")];

  const dockTotal = fmtINR(Number(editableCost) || 0);

  return (
    <div className="sv-qp" id="qp-top">
      {/* Undo / redo strip */}
      <div className="sv-tools">
        <span aria-live="polite">{saveState === "saving" ? "Saving…" : "All changes saved"}</span>
        <button type="button" className="sv-ib sv-ib-soft" onClick={undo} disabled={!canUndo} aria-label="Undo last change"><Icon name="undo" /></button>
        <button type="button" className="sv-ib sv-ib-soft" onClick={redo} disabled={!canRedo} aria-label="Redo"><Icon name="redo" /></button>
      </div>

      {draftOffer && (
        <div className="sv-banner">
          <span>An unsaved draft from {new Date(draftOffer.at || Date.now()).toLocaleString()} was found on this device.</span>
          <div className="sv-banner-b">
            <button type="button" className="sv-btn sv-sm sv-primary" onClick={restoreDraft}>Restore</button>
            <button type="button" className="sv-btn sv-sm sv-soft" onClick={discardDraft}>Discard</button>
          </div>
        </div>
      )}

      {step !== "review" ? (
        /* ───────────── DAYS STEP ───────────── */
        <div onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
          <div className="sv-chips" role="tablist" aria-label="Days" ref={chipsRef}>
            {timeline.map((d, i) => (
              <button key={i} type="button" role="tab" aria-selected={i === activeDay}
                className={"sv-chip" + (i === activeDay ? " on" : "")} onClick={() => goDay(i)}>
                <b>Day {i + 1}</b>
                <span>{d.transit_route ? shortRoute(d).replace(/^Airport to /, "").replace(/^.* to /, "") : "New"}</span>
                {warnDays.has(i) && <i title="Needs attention" />}
              </button>
            ))}
            <button type="button" className="sv-chip add" onClick={addDay} aria-label="Add a day"><Icon name="plus" /></button>
          </div>

          <div className="sv-stack">
            <section className="sv-card sv-stack">
              <div className="sv-dayhead">
                <div>
                  <div className="sv-eyebrow">Day {activeDay + 1} of {timeline.length}</div>
                  <h2 className="sv-h2">{heading}</h2>
                  <div className="sv-sub">{dep ? "Departure day" : (stayValue ? `Night in ${stayValue}` : "No overnight stay chosen")}</div>
                </div>
                <button type="button" className="sv-ib sv-ib-soft" onClick={() => setSheet({ type: "dayMenu" })} aria-label="Day options"><Icon name="more" /></button>
              </div>
              {dayIssues.length
                ? <span className="sv-pill warn">{dayIssues.length} to finish on this day</span>
                : <span className="sv-pill ok"><Icon name="check" size={14} />Day is ready</span>}

              <div className="sv-rail">
                <PickRow label="From" value={rFrom || "Choose"} hint={activeDay > 0 && prevNight && rFrom !== prevNight ? `Day ${activeDay} ended in ${prevNight}` : ""} warn={!rFrom}
                  onClick={() => setSheet({ type: "opts", step: "from" })} />
                <PickRow label="To" value={rTo || "Choose"} warn={!rTo} onClick={() => setSheet({ type: "opts", step: "to" })} />
                {dep
                  ? <PickRow label="Drop" value={endPoint || DEFAULT_POINT} onClick={() => setSheet({ type: "end" })} />
                  : <PickRow label="Stay" value={stayValue || "Choose"} warn={!stayValue} onClick={() => setSheet({ type: "opts", step: "stay" })} />}
              </div>
              {customRoute && <div className="sv-sub">Using “{day.transit_route}”. Pick From or To to replace it.</div>}
              {addNote && <div className="sv-note">{addNote}</div>}
              <div className="sv-act-tools">
                <button type="button" className="sv-btn sv-sm sv-accent" disabled={!!aiBusy} onClick={() => setSheet({ type: "ai" })}>
                  {aiBusy === "day" ? <><span className="sv-spin" />Writing</> : <><Icon name="spark" size={18} />Rewrite day with AI</>}
                </button>
                <button type="button" className="sv-btn sv-sm sv-soft" onClick={() => setSheet({ type: "presets" })}>Ready-made days</button>
              </div>
            </section>

            <section className="sv-card sv-stack">
              {dep ? (
                <div className="sv-row static"><span className="k">Hotel</span><span className="v"><small>Departure day, no hotel needed</small></span></div>
              ) : (
                <>
                  <PickRow label="Hotel" warn={!hotelSelections[activeDay]}
                    value={hotelName || `Choose a hotel${day.overnight_stay ? " in " + day.overnight_stay : ""}`}
                    hint={hotelName ? day.overnight_stay : ""} onClick={() => setSheet({ type: "hotel" })} />
                  <PickRow label="Room" value={day.room_type || DEFAULT_ROOM_TYPE} onClick={() => setSheet({ type: "room" })} />
                  <div className="sv-pair">
                    <Stepper label="Rooms" value={rooms} min={1} max={20} onChange={(v) => setRoomField(activeDay, "rooms", v)} />
                    <Stepper label="Extra bed" value={ebs} min={0} max={20} onChange={(v) => setRoomField(activeDay, "eb", v)} />
                  </div>
                  <div className="sv-sub">Rooms, extra beds and room type also apply to the days after this one.</div>
                </>
              )}
            </section>

            <div className="sv-sechead">
              <h3 className="sv-h3">Activities <span className="sv-sub">{day.schedule.length}</span></h3>
              <button type="button" className="sv-btn sv-sm sv-accent" disabled={!!aiBusy} onClick={() => setSheet({ type: "ai" })}>
                {aiBusy === "day" ? <><span className="sv-spin" />Writing</> : <><Icon name="spark" size={18} />Rewrite day</>}
              </button>
            </div>
            {aiError && <div className="sv-note bad">{aiError}</div>}

            {day.schedule.length === 0 && <div className="sv-card sv-empty">No activities yet. Add one or let AI write the day.</div>}
            {day.schedule.map((slot, k) => {
              const open = openAct === k;
              const noDesc = !String(slot.description || "").trim();
              return (
                <div key={k} className="sv-act">
                  <button type="button" className="sv-act-h" aria-expanded={open} onClick={() => setOpenAct(open ? -1 : k)}>
                    <span className="t">{slot.time_slot || "***"}</span>
                    <span className="m">
                      <b>{slot.activity_title || "Untitled"}</b>
                      {!open && <span className={noDesc ? "empty" : ""}>{noDesc ? "Needs a description" : slot.description}</span>}
                    </span>
                    <Icon name={open ? "up" : "down"} size={18} />
                  </button>
                  {open && (
                    <div className="sv-act-b">
                      <div className="sv-grid-time">
                        <label className="sv-field"><span className="sv-lbl">Time</span>
                          <input className="sv-inp" value={slot.time_slot || ""} onChange={(e) => setAct(k, { time_slot: e.target.value })} /></label>
                        <label className="sv-field"><span className="sv-lbl">Title</span>
                          <input className="sv-inp" value={slot.activity_title || ""} onChange={(e) => setAct(k, { activity_title: e.target.value })} /></label>
                      </div>
                      <label className="sv-field"><span className="sv-lbl">Description</span>
                        <textarea className="sv-inp" rows={4} value={slot.description || ""} onChange={(e) => setAct(k, { description: e.target.value })} /></label>
                      <div className="sv-act-tools">
                        <button type="button" className="sv-btn sv-sm sv-soft" disabled={!!aiBusy} onClick={() => aiWriteActivity(k)}>
                          {aiBusy === "act-" + k ? <><span className="sv-spin" />Writing</> : <><Icon name="spark" size={18} />Write with AI</>}
                        </button>
                        <button type="button" className="sv-btn sv-sm sv-soft sv-sq" disabled={k === 0} onClick={() => moveAct(k, -1)} aria-label="Move up"><Icon name="up" /></button>
                        <button type="button" className="sv-btn sv-sm sv-soft sv-sq" disabled={k === day.schedule.length - 1} onClick={() => moveAct(k, 1)} aria-label="Move down"><Icon name="down" /></button>
                        <button type="button" className="sv-btn sv-sm sv-danger sv-sq" onClick={() => delAct(k)} aria-label="Delete activity"><Icon name="trash" /></button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            <button type="button" className="sv-btn sv-line sv-full" onClick={addAct}><Icon name="plus" />Add activity</button>

            <div className="sv-pair">
              <button type="button" className="sv-btn sv-soft" disabled={activeDay === 0} onClick={() => goDay(activeDay - 1)}><Icon name="back" />Day {activeDay}</button>
              {activeDay === timeline.length - 1
                ? <button type="button" className="sv-btn sv-primary" onClick={() => goStep("review")}>Review<Icon name="chev" /></button>
                : <button type="button" className="sv-btn sv-primary" onClick={() => goDay(activeDay + 1)}>Day {activeDay + 2}<Icon name="chev" /></button>}
            </div>
            <div className="sv-sub sv-center">Tip: swipe left or right to change day.</div>
          </div>
        </div>
      ) : (
        /* ───────────── REVIEW STEP ───────────── */
        <div className="sv-stack">
          <section className="sv-card">
            <h2 className="sv-h2">{quote?.meta_summary?.client_name || "Client"}</h2>
            <div className="sv-sum"><span>Days</span><b>{timeline.length}</b></div>
            <div className="sv-sum"><span>Guests</span><b>{quote?.meta_summary?.adults ?? quote?.adults ?? 2} adults{(quote?.meta_summary?.kids ?? quote?.kids ?? 0) ? `, ${quote?.meta_summary?.kids ?? quote?.kids} kids` : ""}</b></div>
            <div className="sv-sum"><span>Plan</span><b>{quote?.meta_summary?.budget_tier || "N/A"} · {mealPlan} · {vehicleType || "N/A"}</b></div>
            <PickRow label="Pick-up" value={startPoint || DEFAULT_POINT} onClick={() => setSheet({ type: "start" })} />
            <PickRow label="Drop" value={endPoint || DEFAULT_POINT} onClick={() => setSheet({ type: "end" })} />
            {[["start", "Start", startPoint], ["end", "End", endPoint]].map(([key, label, val]) => {
              if (isSrinagarPoint(val) || (val || "").trim().length < 3) return null;
              const info = key === "start" ? startInfo : endInfo;
              return (
                <div key={key} className="sv-loc">
                  <div className="sv-sub"><b>{label} point:</b> {val}</div>
                  <button type="button" className="sv-btn sv-sm sv-soft sv-self" disabled={!!locBusy} onClick={() => locatePoint(key)}>
                    {locBusy === key ? <><span className="sv-spin" />Looking up</> : <><Icon name="pin" size={18} />Find location and distance (AI)</>}
                  </button>
                  {info && (
                    <div className="sv-loc-g">
                      {[["lat", "Lat", "0.0001"], ["lon", "Lon", "0.0001"], ["km", "Road km", "1"], ["hours", "Hours", "0.5"]].map(([f, l, st]) => (
                        <label key={f} className="sv-field"><span className="sv-lbl">{l}</span>
                          <input className="sv-inp" type="number" inputMode="decimal" step={st} value={info[f] ?? ""} onChange={(e) => editInfo(key, f, e.target.value)} /></label>
                      ))}
                    </div>
                  )}
                  {locMsg[key] && <div className={"sv-sub" + (info ? "" : " bad")}>{locMsg[key]}</div>}
                </div>
              );
            })}
          </section>

          <section className="sv-card sv-stack">
            <div className="sv-sechead">
              <h3 className="sv-h3">Checks</h3>
              {issues.length ? <span className="sv-pill warn">{issues.length} to finish</span> : <span className="sv-pill ok">All set</span>}
            </div>
            {issues.length === 0 && <div className="sv-sub">Every day has a route, a hotel and descriptions. Ready for the PDF.</div>}
            {issues.map((q, k) => (
              <div key={k} className="sv-issue"><span>{q.text}</span><button type="button" className="sv-btn sv-sm" onClick={() => runFix(q)}>{q.btn === "Open day" ? "Open" : q.btn === "Pick suggested hotel" ? "Pick one" : q.btn}</button></div>
            ))}
            {missingHotelDays.length > 1 && <button type="button" className="sv-btn sv-sm sv-soft sv-self" onClick={fixAllHotels}>Pick suggested hotels for all ({missingHotelDays.length})</button>}
          </section>

          <section className="sv-card">
            <h3 className="sv-h3">Stays</h3>
            {timeline.map((d, i) => isDepDay(d) ? null : (
              <button key={i} type="button" className="sv-sum link" onClick={() => { setActiveDay(i); onStep("days"); }}>
                <span>Day {i + 1} · {d.overnight_stay || "?"}</span>
                <b className={hotelSelections[i] ? "" : "bad"}>
                  {hotelSelections[i] ? ALL_HOTELS_FLAT[hotelSelections[i]]?.name : "Not chosen"}
                  <small>{d.room_type || DEFAULT_ROOM_TYPE} · {d.rooms ?? 1} room{(d.rooms ?? 1) > 1 ? "s" : ""}{d.eb ? `, ${d.eb} extra bed` : ""}</small>
                </b>
              </button>
            ))}
          </section>

          <section className="sv-card sv-stack">
            <label className="sv-field"><span className="sv-lbl">Total price on the PDF (₹)</span>
              <input className="sv-inp sv-big" type="number" inputMode="numeric" value={editableCost} onChange={(e) => setEditableCost(e.target.value)} /></label>
            <button type="button" className={"sv-sw" + (showPerPerson ? " on" : "")} role="switch" aria-checked={showPerPerson} onClick={() => setShowPerPerson((v) => !v)}>
              <span>Show price per person</span><i className="box" /></button>
            <span className="sv-lbl">Included in the package</span>
            <div className="sv-stack" style={{ border: "1.5px solid var(--sv-line)", borderRadius: 14, padding: 12, gap: 10 }}>
              <span className="sv-lbl" style={{ color: "var(--sv-ink)", margin: 0 }}>Union cab included for</span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {[["union_cab_pahalgam", "Pahalgam"], ["union_cab_gulmarg", "Gulmarg"], ["union_cab_sonamarg", "Sonamarg"], ["union_cab_other", "Other"]].map(([k, lab]) => {
                  const on = includedExtras.includes(k);
                  return <button key={k} type="button" className={"sv-btn " + (on ? "sv-primary" : "sv-soft")} aria-pressed={on} onClick={() => toggleExtra(k)}>{on ? "✓ " : ""}{lab}</button>;
                })}
              </div>
              {includedExtras.includes("union_cab_other") && (
                <div className="sv-stack" style={{ gap: 8 }}>
                  <label className="sv-sub" htmlFor="cab-other-in">Other place(s). Type a name and tap Add.</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input id="cab-other-in" className="sv-inp" value={otherIn} maxLength={40} placeholder="e.g. Doodhpathri" autoComplete="off"
                      onChange={(e) => setOtherIn(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addOtherPlace(); } }} />
                    <button type="button" className="sv-btn sv-accent" disabled={!otherIn.trim()} onClick={addOtherPlace}>Add</button>
                  </div>
                  {cabOtherPlaces.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                      {cabOtherPlaces.map((p, i) => (
                        <button key={p} type="button" className="sv-btn sv-soft" style={{ minHeight: 40 }} aria-label={"Remove " + p}
                          onClick={() => setCabOtherPlaces((a) => a.filter((_, j) => j !== i))}>{p} ×</button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            {[["gondola_p1", "Gondola Phase 1"], ["gondola_p2", "Gondola Phase 2"]].map(([k, lab]) => (
              <button key={k} type="button" className={"sv-sw" + (includedExtras.includes(k) ? " on" : "")} role="switch" aria-checked={includedExtras.includes(k)} onClick={() => toggleExtra(k)}>
                <span>{lab}</span><i className="box" /></button>
            ))}
            <span className="sv-lbl">Your own inclusions</span>
            {customIncl.length === 0 && <div className="sv-sub">None yet.</div>}
            {customIncl.map((c, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <button type="button" className={"sv-sw" + (c.on ? " on" : "")} role="switch" aria-checked={c.on}
                  onClick={() => setCustomIncl((a) => a.map((x, j) => (j === i ? { ...x, on: !x.on } : x)))}>
                  <span style={{ overflowWrap: "anywhere" }}>{c.t}</span><i className="box" /></button>
                <button type="button" className="sv-btn sv-danger" style={{ minHeight: 40, padding: "0 12px" }} aria-label={"Delete " + c.t}
                  onClick={() => setCustomIncl((a) => a.filter((_, j) => j !== i))}>×</button>
              </div>
            ))}
            <div style={{ display: "flex", gap: 8 }}>
              <input id="incl-in" className="sv-inp" value={inclIn} maxLength={80} placeholder="e.g. Pony ride at Pahalgam" autoComplete="off" aria-label="New inclusion"
                onChange={(e) => setInclIn(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCustomIncl(); } }} />
              <button type="button" className="sv-btn sv-accent" disabled={!inclIn.trim() || customIncl.length >= 8} onClick={addCustomIncl}>Add</button>
            </div>
            <div className="sv-sub">Switched on, an inclusion prints under What's included on the PDF. Switched off, it is left out. Up to 8.</div>
            {coupleOn && <div className="sv-sub">Couple add-ons from the Trip step: {(trip?.coupleExtras || []).length ? (trip.coupleExtras || []).map((k) => ({ couple_cake: "Cake Cutting Celebration", couple_bed: "Bed decoration", couple_candle: "Candle light dinner" })[k]).join(", ") : "none ticked"}.</div>}
            <div className="sv-sub">Anything switched off is listed under exclusions on the PDF.</div>
          </section>

          <details className="sv-more">
            <summary><b>Hotels &amp; photos</b><span className="sv-sub">add a hotel or its photos</span></summary>
            <HotelImageManager />
          </details>
        </div>
      )}

      {/* Always-visible total + main action */}
      <div className="sv-dock">
        <div className="sv-dock-tot"><small>Estimated total</small><b>{dockTotal}</b></div>
        {step === "review"
          ? <button type="button" className="sv-btn sv-accent" onClick={generateChecked} disabled={pdfBusy}>{pdfBusy ? <><span className="sv-spin" />Generating</> : <><Icon name="pdf" />Generate PDF</>}</button>
          : <button type="button" className="sv-btn sv-primary" onClick={() => goStep("review")}>Review &amp; PDF{issues.length > 0 && <span className="sv-badge">{issues.length}</span>}</button>}
      </div>

      {/* ───────────── SHEETS ───────────── */}
      {sheet?.type === "opts" && (() => {
        const st = sheet.step, list = optionList(st), cur = optionValue(st), isAddHere = addOpen === st;
        return (
          <Sheet title={sheetTitle[st]} onClose={closeSheet}>
            {st === "from" && activeDay > 0 && prevNight && <div className="sv-sub">Day {activeDay} ended in {prevNight}.</div>}
            <div className="sv-opts">
              {list.map((o) => {
                const isCustom = customNames().includes(o);
                return (
                  <div key={o} className={"sv-opt-wrap" + (isCustom ? " has-x" : "")}>
                    <button type="button" className={"sv-opt" + (cur === o ? " on" : "")} onClick={() => choose(st, o)}>{o}</button>
                    {isCustom && <button type="button" className="sv-opt-x" aria-label={`Remove ${o}`} onClick={() => removeCustomPlace(o)}><Icon name="x" size={16} /></button>}
                  </div>
                );
              })}
            </div>
            {addNote && <div className="sv-note">{addNote}</div>}
            {!isAddHere
              ? <button type="button" className="sv-opt add" onClick={() => { setAddOpen(st); setAddText(""); setAddErr(""); }}>+ Add a new place</button>
              : (
                <div className="sv-addplace">
                  <input autoFocus className="sv-inp" placeholder="Place name, e.g. Sopore" maxLength={40} value={addText} disabled={addBusy}
                    onChange={(e) => setAddText(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCustomPlace(addText, (n) => choose(st, n)); } }} />
                  <button type="button" className="sv-btn sv-primary" disabled={addBusy || !addText.trim()} onClick={() => addCustomPlace(addText, (n) => choose(st, n))}>{addBusy ? "Locating…" : "Add and use it"}</button>
                  {addErr && <div className="sv-note bad">{addErr}</div>}
                </div>
              )}
          </Sheet>
        );
      })()}

      {sheet?.type === "hotel" && (
        <Sheet title={`Hotel in ${day.overnight_stay || "this place"}`} onClose={closeSheet}>
          {hotelList.length === 0 && <div className="sv-empty">No hotels saved for {day.overnight_stay || "this place"} yet. Add one under Hotels &amp; photos in Review.</div>}
          {hotelList.length > 6 && (
            <div className="sv-find">
              <input className="sv-inp" type="search" placeholder={`Search ${hotelList.length} hotels`} value={hotelQ} onChange={(e) => setHotelQ(e.target.value)} />
            </div>
          )}
          <div className="sv-list">
            {hotelList.filter((h) => !hotelQ.trim() || (h.name + " " + (h.place || "")).toLowerCase().includes(hotelQ.trim().toLowerCase())).map((h) => (
              <button key={h.id} type="button" className={"sv-opt" + (hotelSelections[activeDay] === h.id ? " on" : "")}
                onClick={() => { setHotelSelections((prev) => ({ ...prev, [activeDay]: h.id })); closeSheet(); }}>
                {h.name}<small>{h.place}</small>
              </button>
            ))}
          </div>
        </Sheet>
      )}

      {sheet?.type === "room" && (
        <Sheet title="Room type" onClose={closeSheet}>
          <div className="sv-opts">
            {[...new Set([day.room_type || DEFAULT_ROOM_TYPE, ...ROOM_TYPES])].map((t) => (
              <button key={t} type="button" className={"sv-opt" + ((day.room_type || DEFAULT_ROOM_TYPE) === t ? " on" : "")}
                onClick={() => { setRoomField(activeDay, "room_type", t); closeSheet(); }}>{t}</button>
            ))}
          </div>
          <div className="sv-sub">Applies to this day and the days after it.</div>
        </Sheet>
      )}

      {sheet?.type === "presets" && (
        <Sheet title="Ready-made days" onClose={closeSheet}>
          <div className="sv-list">
            {TRANSIT_OPTIONS.map((route) => (
              <button key={route} type="button" className={"sv-opt" + (day.transit_route === route ? " on" : "")}
                onClick={() => { applyRoute(route); closeSheet(); }}>{routeLabel(route, startPoint, endPoint)}</button>
            ))}
          </div>
          <div className="sv-sub">This replaces the route and activities of the current day.</div>
        </Sheet>
      )}

      {(sheet?.type === "start" || sheet?.type === "end") && (
        <Sheet title={sheet.type === "start" ? "Pick-up point" : "Drop point"} onClose={closeSheet}>
          <div className="sv-list">
            {(sheet.type === "start" ? POINT_PRESETS : endOptions).map((p) => {
              const cur = sheet.type === "start" ? (startPoint || DEFAULT_POINT) : (endPoint || DEFAULT_POINT);
              return (
                <button key={p} type="button" className={"sv-opt" + (cur === p ? " on" : "")}
                  onClick={() => { (sheet.type === "start" ? changeStart : changeEnd)(p); closeSheet(); }}>{p}</button>
              );
            })}
          </div>
        </Sheet>
      )}

      {sheet?.type === "dayMenu" && (
        <Sheet title={`Day ${activeDay + 1} options`} onClose={closeSheet}>
          <button type="button" className="sv-menu" disabled={activeDay === 0} onClick={() => { moveDay(activeDay, -1); closeSheet(); }}><Icon name="up" />Move earlier</button>
          <button type="button" className="sv-menu" disabled={activeDay === timeline.length - 1} onClick={() => { moveDay(activeDay, 1); closeSheet(); }}><Icon name="down" />Move later</button>
          <button type="button" className="sv-menu" onClick={() => { copyDay(activeDay); closeSheet(); }}><Icon name="copy" />Duplicate this day</button>
          <button type="button" className="sv-menu danger" disabled={timeline.length <= 1} onClick={() => { closeSheet(); deleteDay(activeDay); }}><Icon name="trash" />Delete this day</button>
          <div className="sv-sub">Delete can be undone from the top bar.</div>
        </Sheet>
      )}

      {sheet?.type === "ai" && (
        <Sheet title={`Rewrite Day ${activeDay + 1} with AI`} onClose={closeSheet}>
          <label className="sv-field"><span className="sv-lbl">Hints (optional)</span>
            <input className="sv-inp" maxLength={300} placeholder="honeymoon, relaxed pace…" value={aiHints} onChange={(e) => setAiHints(e.target.value)} /></label>
          <button type="button" className="sv-btn sv-accent sv-full" onClick={() => { closeSheet(); aiRewriteDay(); }}><Icon name="spark" size={18} />Write this day</button>
          <div className="sv-sub">This replaces all activities for the day. Undo brings them back.</div>
        </Sheet>
      )}
    </div>
  );
}
