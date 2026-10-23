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
const PICKUP_ROUTE = "Airport Pickup and Local Sightseeing: Overnight Srinagar";
const DROP_ROUTE   = "Airport Drop-Departure";
// Day 1 can end in any base: "Airport Pickup ...: Overnight <City>".
const isPickupRoute = (r) => /^Airport Pickup/i.test(r || "");
const pickupCity = (r) => ((r || "").match(/Overnight\s+(\w+)/i) || [])[1] || "Srinagar";
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
const PICK_FROM  = ["Airport", "Srinagar", "Pahalgam", "Gulmarg", "Sonamarg"];
const PICK_TO    = ["Local sightseeing", "Srinagar", "Pahalgam", "Gulmarg", "Sonamarg", "Doodhpathri", "Departure"];
const PICK_NIGHT = ["Srinagar", "Pahalgam", "Gulmarg", "Sonamarg"];

function defaultNightFor(to, from) {
  if (PICK_NIGHT.includes(to)) return to;                       // going to a base: sleep there
  if (from === "Airport") return "Srinagar";
  return PICK_NIGHT.includes(from) ? from : "Srinagar";         // sightseeing / day trip: back where you started
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
  if ((m = r.match(/^Airport Pickup and Local Sightseeing: Overnight (\w+)$/i))) return { from: "Airport", to: "Local sightseeing", night: m[1] };
  if ((m = r.match(/^Airport Pickup: Overnight (\w+)$/i)))                       return { from: "Airport", to: m[1], night: m[1] };
  if ((m = r.match(/^(\w+) Local Sightseeing: Overnight (\w+)$/i)))              return { from: m[1], to: "Local sightseeing", night: m[2] };
  if ((m = r.match(/^(\w+) to (\w+): Overnight (\w+)$/i)))                       return { from: m[1], to: m[2], night: m[3] };
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
    const m = (day.transit_route || "").match(/^(\w+) to (\w+)/i);
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

function getHotelGroup(overnight_stay = "") {
  const s = overnight_stay.toLowerCase();
  if (s.includes("pahalgam")) return "pahalgam";
  if (s.includes("gulmarg"))  return "gulmarg";
  if (s.includes("sonamarg")) return "sonamarg";
  return "srinagar";
}

const ALL_HOTELS_FLAT = Object.values(HOTEL_KB).flat().reduce((acc, h) => {
  acc[h.id] = h;
  return acc;
}, {});

// Hotels added from the admin "Hotels" tab are merged into HOTEL_KB / ALL_HOTELS_FLAT in place,
// so every picker, the cost dashboard and the photo manager see them without further changes.
export async function loadCustomHotels() {
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
      const group = String(h.place || "").toLowerCase();
      if (!HOTEL_KB[group]) return;
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

function HotelCostDashboard({ hotelSelections = {}, timeline = [], onTotalChange }) {
  const buildRows = (prev = {}) => {
    const next = {};
    Object.values(hotelSelections).forEach((hotelId) => {
      if (!hotelId || !ALL_HOTELS_FLAT[hotelId]) return;
      next[hotelId] = prev[hotelId] || {
        hotelId, stays: 1, rooms: 1, eb: 0, cnb: 0, roomRate: 0, ebRate: 0,
      };
    });
    return next;
  };

  const [rows, setRows]       = React.useState(() => buildRows());
  const [cabCost, setCabCost] = React.useState(0);

  React.useEffect(() => { setRows((prev) => buildRows(prev)); }, [hotelSelections]);

  React.useEffect(() => {
    if (onTotalChange) {
      const hotelTotal = Object.values(rows).reduce((sum, r) => sum + calcRowTotal(r), 0);
      onTotalChange(hotelTotal + (Number(cabCost) || 0));
    }
  }, [rows, cabCost]);

  const handleChange = (hotelId, field, value) => {
    setRows((prev) => ({ ...prev, [hotelId]: { ...prev[hotelId], [field]: value } }));
  };

  const hotelDaysMap = {};
  Object.entries(hotelSelections).forEach(([dayIdx, hotelId]) => {
    if (!hotelId) return;
    if (!hotelDaysMap[hotelId]) hotelDaysMap[hotelId] = [];
    hotelDaysMap[hotelId].push(Number(dayIdx) + 1);
  });

  const rowList    = Object.values(rows);
  const hotelTotal = rowList.reduce((sum, r) => sum + calcRowTotal(r), 0);
  const grandTotal = hotelTotal + (Number(cabCost) || 0);

  const thStyle = {
    padding: "8px 10px", backgroundColor: "#f1f5f9", color: "#475569",
    fontWeight: "700", fontSize: "0.73rem", textTransform: "uppercase",
    letterSpacing: "0.4px", borderBottom: "1px solid #e2e8f0",
    whiteSpace: "nowrap", textAlign: "left",
  };
  const tdStyle = {
    padding: "8px 10px", borderBottom: "1px solid #f1f5f9",
    color: "#0f172a", verticalAlign: "middle",
  };
  const numInput = {
    width: "64px", padding: "5px 6px", border: "1px solid #cbd5e1",
    borderRadius: "6px", fontSize: "0.82rem", color: "#0f172a",
    backgroundColor: "#f8fafc", textAlign: "center", minHeight: "36px",
    boxSizing: "border-box",
  };

  return (
    <>
      <style>{`
        .hcd-totals {
          display: flex;
          justify-content: flex-end;
          align-items: center;
          gap: 20px;
          margin-top: 14px;
          padding-top: 12px;
          border-top: 2px solid #e2e8f0;
          flex-wrap: wrap;
        }
        .hcd-divider { width: 1px; height: 24px; background: #e2e8f0; }
        @media (max-width: 600px) {
          .hcd-totals { flex-direction: column; align-items: flex-start; gap: 12px; }
          .hcd-divider { display: none; }
          .hcd-cab-input { width: 100% !important; box-sizing: border-box; }
        }
      `}</style>
      <div style={{ marginTop: "32px", backgroundColor: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "12px", padding: "clamp(14px, 4vw, 20px) clamp(14px, 4vw, 24px)", fontFamily: "system-ui, sans-serif" }}>
        <div style={{ marginBottom: "14px", paddingBottom: "12px", borderBottom: "1px solid #e2e8f0" }}>
          <p style={{ margin: 0, fontSize: "1rem", fontWeight: "700", color: "#0f172a" }}>🏨 Hotel Cost Breakdown</p>
          <p style={{ margin: "3px 0 0", fontSize: "0.78rem", color: "#64748b" }}>
            Hotels auto-fetched from assignments above · Formula: (Nights × Rooms × Room Rate) + (Nights × EB × EB Rate) + Trip Cab Cost
          </p>
        </div>

        {rowList.length === 0 ? (
          <p style={{ textAlign: "center", color: "#94a3b8", fontSize: "0.85rem", padding: "24px 0" }}>
            No hotels assigned yet. Use the hotel picker above for each day — they will appear here automatically.
          </p>
        ) : (
          <>
            <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", minWidth: "560px" }}>
                <thead>
                  <tr>
                    <th style={thStyle}>Hotel</th>
                    <th style={thStyle}>Assigned Days</th>
                    <th style={thStyle}>Nights</th>
                    <th style={thStyle}>Rooms</th>
                    <th style={thStyle}>EB</th>
                    <th style={thStyle}>CNB</th>
                    <th style={thStyle}>Room Rate/Night (₹)</th>
                    <th style={thStyle}>EB Rate/Night (₹)</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Total (₹)</th>
                  </tr>
                </thead>
                <tbody>
                  {rowList.map((row) => {
                    const hotel = ALL_HOTELS_FLAT[row.hotelId];
                    const days  = (hotelDaysMap[row.hotelId] || []).sort((a, b) => a - b);
                    return (
                      <tr key={row.hotelId}>
                        <td style={tdStyle}>
                          <div style={{ fontWeight: "600", color: "#1e293b" }}>{hotel.name}</div>
                          <div style={{ fontSize: "0.72rem", color: "#94a3b8", marginTop: "1px" }}>📍 {hotel.place}</div>
                        </td>
                        <td style={tdStyle}>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                            {days.map((d) => (
                              <span key={d} style={{ padding: "2px 7px", borderRadius: "999px", backgroundColor: "#eff6ff", color: "#1d4ed8", fontSize: "0.72rem", fontWeight: "700" }}>Day {d}</span>
                            ))}
                          </div>
                        </td>
                        {["stays","rooms","eb","cnb","roomRate","ebRate"].map((field) => (
                          <td key={field} style={tdStyle}>
                            <input type="number" min="0" style={numInput} value={row[field]} onChange={(e) => handleChange(row.hotelId, field, e.target.value)} />
                          </td>
                        ))}
                        <td style={{ ...tdStyle, textAlign: "right", fontWeight: "700", color: "#0284c7" }}>
                          {fmtINR(calcRowTotal(row))}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="hcd-totals">
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <span style={{ fontSize: "0.82rem", color: "#475569", fontWeight: "600" }}>🏨 Hotel Subtotal:</span>
                <span style={{ fontSize: "1rem", fontWeight: "700", color: "#0284c7" }}>{fmtINR(hotelTotal)}</span>
              </div>
              <div className="hcd-divider" />
              <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                <label style={{ fontSize: "0.82rem", color: "#854d0e", fontWeight: "600", whiteSpace: "nowrap" }}>🚗 Cab Cost – Full Trip (₹):</label>
                <input type="number" min="0" value={cabCost} onChange={(e) => setCabCost(e.target.value)} className="hcd-cab-input" style={{ width: "110px", padding: "6px 8px", border: "1px solid #fde047", borderRadius: "6px", fontSize: "0.88rem", color: "#854d0e", backgroundColor: "#fef9c3", textAlign: "center", fontWeight: "600", minHeight: "36px" }} />
              </div>
              <div className="hcd-divider" />
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <span style={{ fontSize: "0.9rem", color: "#0f172a", fontWeight: "700" }}>Grand Total:</span>
                <span style={{ fontSize: "1.25rem", fontWeight: "800", color: "#10b981" }}>{fmtINR(grandTotal)}</span>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
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

  const groupLabels = { srinagar: "Srinagar", pahalgam: "Pahalgam", gulmarg: "Gulmarg", sonamarg: "Sonamarg" };

  return (
    <div style={{ marginTop: "40px", backgroundColor: "#fff", border: "1px solid #e2e8f0", borderRadius: "14px", overflow: "hidden", fontFamily: "system-ui, sans-serif" }}>
      {/* Header */}
      <div style={{ padding: "18px clamp(14px, 4vw, 24px)", borderBottom: "1px solid #e2e8f0", background: "linear-gradient(135deg, #1e3a4f 0%, #0f2a3a 100%)", color: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "1.35rem" }}>🖼️</span>
          <div>
            <p style={{ margin: 0, fontSize: "1rem", fontWeight: "700" }}>Hotel Photo Manager</p>
            <p style={{ margin: "2px 0 0", fontSize: "0.78rem", opacity: 0.75 }}>
              Add reference photos for each hotel — these appear in the generated PDF quotation.
            </p>
          </div>
        </div>
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
                <h4 style={{ margin: "0 0 4px", fontSize: "1rem", color: "#0f172a", fontWeight: "700" }}>
                  {selectedHotel?.name}
                </h4>
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
export default function QuotePreview({ quote }) {
  const [timeline,        setTimeline]        = useState(quote?.itinerary_timeline || []);
  const [activeDay,       setActiveDay]       = useState(0);
  const [editableCost,    setEditableCost]    = useState(quote?.financial_summary?.total_payable_inr || 38500);
  const [hotelSelections, setHotelSelections] = useState({});
  const [startPoint,      setStartPoint]      = useState(quote?.meta_summary?.start_point || DEFAULT_POINT);
  const [endPoint,        setEndPoint]        = useState(quote?.meta_summary?.end_point   || DEFAULT_POINT);

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
    const overnightMatch = route.match(/Overnight\s+(\w+)/i);
    const derivedCity = overnightMatch ? overnightMatch[1] : null;
    if (derivedCity) {
      const hotelGroup = HOTEL_KB[derivedCity.toLowerCase()] || HOTEL_KB["srinagar"];
      setHotelSelections(prev => ({ ...prev, [idx]: hotelGroup[0].id }));
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
    setTimeline((prev) => [...prev, { day: n, title: "", date: `Day ${n} Plan`, transit_route: "", overnight_stay: night, schedule: [] }]);
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
          const canFix = PICK_FROM.includes(prev.overnight_stay) && p.to !== "Departure";
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

  // Undo / redo: edits are grouped (0.6 s) into history steps; a draft is also kept in this browser.
  const hist = useRef({ past: [], future: [], last: null, restoring: false });
  const [, setHistTick] = useState(0);
  const [saveState, setSaveState] = useState("saved");
  const [draftOffer, setDraftOffer] = useState(null);
  const draftKey = "qp-draft:" + (quote?.meta_summary?.client_name || "client");
  const saveDraft = (snap) => {
    try {
      localStorage.setItem(draftKey, JSON.stringify({ ...snap, startPoint, endPoint, editableCost, at: Date.now() }));
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
                    client_email: quote?.meta_summary?.client_email || "N/A",
                    days: timeline.length || quote?.meta_summary?.total_days || 5,
                    start_date: quote?.meta_summary?.start_date || quote?.start_date || "Flexible",
                    adults: quote?.meta_summary?.adults || quote?.adults || 2,
                    kids: quote?.meta_summary?.kids ?? quote?.kids ?? 0,
                    budget_tier: quote?.meta_summary?.budget_tier || "Mid-Range",
                    trip_pace: quote?.meta_summary?.trip_pace || "Moderate",
                    custom_cost: editableCost,
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
        .qp-gen { border: 0; background: #7c3aed; color: #fff; border-radius: 8px; min-height: 40px; padding: 0 18px; font-weight: 700; cursor: pointer; }
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
        @media (max-width: 420px) {
          .qp-activity-row { flex-direction: column; align-items: stretch; }
          .qp-time-input, .qp-title-input { width: 100%; }
        }
      `}</style>

      <div className="qp-wrap">
        {/* 1. Dashboard Header */}
        <div style={{ marginBottom: "24px", paddingBottom: "16px", borderBottom: "1px solid " + UI_THEME.colors.border }}>
          <h2 style={{ fontSize: "clamp(1.3rem, 4vw, 1.75rem)", fontWeight: "800", color: UI_THEME.colors.primary, margin: "0 0 6px 0" }}>
            ✨ Live Itinerary Preview & Customizer
          </h2>
          <p style={{ margin: 0, fontSize: "0.9rem", color: UI_THEME.colors.textLight }}>
            Review or edit the day-by-day plan details below before saving.
          </p>
        </div>

        {/* 2. Sticky summary bar */}
        <div className="qp-sticky">
          <div><div className="k">Client</div><div className="v">{quote?.meta_summary?.client_name || "N/A"}</div></div>
          <div><div className="k">Trip</div><div className="v">{timeline.length} days · {quote?.meta_summary?.budget_tier || "N/A"} · {quote?.meta_summary?.vehicle_type || "N/A"}</div></div>
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

        {/* Tour start / end points */}
        <div style={{ background: "#fff", border: "1px solid " + UI_THEME.colors.border, borderRadius: "12px", padding: "14px 18px", marginBottom: "20px", boxShadow: UI_THEME.shadows.sm }}>
          <div style={{ fontWeight: "700", color: "#334155", fontSize: "0.9rem", marginBottom: "10px" }}>🧭 Tour Start &amp; End Point</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "14px" }}>
            {[["Tour starts from (Day 1 pickup)", startPoint, changeStart, "start"], ["Tour ends at (last-day drop)", endPoint, changeEnd, "end"]].map(([label, val, setter, key]) => {
              const isCustom = !POINT_PRESETS.includes(val);
              return (
                <div key={key}>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#64748b", marginBottom: "4px" }}>{label}</label>
                  <select
                    className="qp-route-select"
                    value={isCustom ? "__custom" : val}
                    onChange={(e) => setter(e.target.value === "__custom" ? "" : e.target.value)}
                  >
                    {POINT_PRESETS.map((p) => <option key={p} value={p}>{p}</option>)}
                    <option value="__custom">Other (type below)…</option>
                  </select>
                  {isCustom && (
                    <input
                      className="qp-route-select"
                      style={{ marginTop: "6px" }}
                      placeholder="e.g. Delhi Airport, Udhampur Railway Station"
                      value={val}
                      onChange={(e) => setter(e.target.value)}
                    />
                  )}
                  {!isSrinagarPoint(val) && val.trim().length >= 3 && (() => {
                    const info = key === "start" ? startInfo : endInfo;
                    const small = { width: "78px", padding: "4px 6px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "0.8rem", boxSizing: "border-box" };
                    return (
                      <div style={{ marginTop: "6px" }}>
                        <button type="button" onClick={() => locatePoint(key)} disabled={!!locBusy}
                          style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid #c4b5fd", background: "#f5f3ff", color: "#6d28d9", fontWeight: "bold", cursor: locBusy ? "wait" : "pointer", fontSize: "0.8rem" }}>
                          {locBusy === key ? "Looking up…" : "📍 Find location & distance (AI)"}
                        </button>
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
                  })()}
                </div>
              );
            })}
          </div>
          <p style={{ margin: "8px 0 0", fontSize: "0.75rem", color: "#94a3b8" }}>
            Updates the pickup / drop days and the PDF. Applies to the days using the “Airport Pickup…” (any overnight city) and “Airport Drop-Departure” routes (their descriptions are regenerated).
          </p>
        </div>

        {/* 3. Trip overview strip */}
        <h3 style={{ margin: "0 0 8px 0", fontSize: "1rem", color: "#0f172a" }}>
          Trip overview <span style={{ fontWeight: 500, fontSize: "0.8rem", color: "#475569" }}>· click a day to edit it; use the buttons under it to move, copy or remove</span>
        </h3>
        <div className="qp-ov">
          {timeline.map((d, i) => {
            const dep = isDepDay(d);
            const hot = flatHotels[hotelSelections[i]];
            return (
              <div key={i} className={"qp-ovcard" + (i === activeDay ? " on" : "")}>
                <button type="button" className="qp-ovmain" onClick={() => { setActiveDay(i); setTimeout(() => { const el = document.getElementById("qp-editor"); if (el && el.scrollIntoView) el.scrollIntoView({ behavior: "smooth", block: "start" }); }, 0); }} aria-label={`Edit day ${i + 1}`}>
                  <span className="qp-ovdn"><span>Day {i + 1}</span>{warnDays.has(i) && <span className="qp-ovdot" title="Needs attention" />}</span>
                  <span className="qp-ovrt">{shortRoute(d)}</span>
                  <span className="qp-ovnt">{dep ? "No overnight" : (d.overnight_stay ? `Night in ${d.overnight_stay}` : "—")}</span>
                  <span className={"qp-ovhot" + (!dep && !hot ? " bad" : "")}>{dep ? "Drop-off" : (hot ? hot.name : "No hotel yet")}</span>
                </button>
                <div className="qp-ovacts">
                  <button type="button" onClick={() => moveDay(i, -1)} disabled={i === 0} aria-label="Move day earlier">&#8249;</button>
                  <button type="button" onClick={() => moveDay(i, 1)} disabled={i === timeline.length - 1} aria-label="Move day later">&#8250;</button>
                  <button type="button" onClick={() => copyDay(i)} aria-label="Duplicate day">Copy</button>
                  <button type="button" onClick={() => deleteDay(i)} disabled={timeline.length <= 1} aria-label="Delete day">Del</button>
                </div>
              </div>
            );
          })}
          <button type="button" className="qp-ovadd" onClick={addDay}>+ Add day</button>
        </div>

        {/* Checks */}
        <div className="qp-checks">
          <div style={{ fontWeight: 800, fontSize: "0.95rem", color: "#0f172a" }}>
            Checks <span className={"qp-badge" + (issues.length ? "" : " ok")}>{issues.length ? `${issues.length} ${issues.length === 1 ? "issue" : "issues"}` : "Ready"}</span>
          </div>
          {issues.length === 0 && (
            <div style={{ background: "#f0fdf4", border: "1px solid #86efac", borderRadius: "10px", padding: "10px 12px", fontSize: "0.85rem", fontWeight: 600, color: "#14532d" }}>
              Everything looks consistent. Ready to generate the PDF.
            </div>
          )}
          {issues.map((w, k) => (
            <div key={k} className="qp-warn"><span>{w.text}</span><button type="button" className="qp-fix" onClick={w.fix}>{w.btn}</button></div>
          ))}
        </div>

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
            <h3 style={{ margin: "0 0 15px 0", color: "#0f172a", fontSize: "clamp(1rem, 3vw, 1.2rem)" }}>
              📍 Day {timeline[activeDay].day}: {timeline[activeDay].title || timeline[activeDay].date}
            </h3>

            {/* Route picker: Starting from -> Going to -> Overnight */}
            {(() => {
              const day = timeline[activeDay];
              const parsed = parseRoute(day.transit_route);
              const draft = pickDraft[activeDay] || {};
              const prevNight = activeDay > 0 ? (timeline[activeDay - 1]?.overnight_stay || "") : "";
              const autoFrom = activeDay === 0 ? "Airport" : (PICK_FROM.includes(prevNight) ? prevNight : "Srinagar");
              const from  = draft.from  ?? parsed?.from  ?? autoFrom;
              const to    = draft.to    ?? parsed?.to    ?? "";
              const isDep = to === "Departure";
              const night = isDep ? "" : (draft.night ?? parsed?.night ?? "");
              const customRoute = !parsed && !!day.transit_route;

              const pick = (patch) => {
                const next = { from, to, night, ...patch };
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
                padding: "8px 16px", borderRadius: "20px", minHeight: "40px", fontSize: "0.85rem", fontWeight: "bold",
                border: on ? "2px solid #2563eb" : "1px solid #cbd5e1", backgroundColor: on ? "#2563eb" : "#fff",
                color: on ? "#fff" : "#1e293b", cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.45 : 1, transition: "all 0.15s",
              });
              const row = (step, label, hint, options, value, onPick, disabled) => (
                <div style={{ marginBottom: "14px" }}>
                  <label style={{ fontWeight: "bold", color: "#334155", display: "block", marginBottom: "6px", fontSize: "0.9rem" }}>
                    {step}. {label} {hint && <span style={{ fontWeight: 500, color: "#64748b", fontSize: "0.8rem" }}>{hint}</span>}
                  </label>
                  <div className="qp-city-btns" style={{ marginTop: 0 }}>
                    {options.map((o) => (
                      <button key={o} type="button" disabled={disabled} onClick={() => onPick(o)} style={chipStyle(value === o, disabled)}>{o}</button>
                    ))}
                  </div>
                </div>
              );

              return (
                <div id="day-route-select">
                  <div style={{ marginBottom: "14px" }}>
                    <label style={{ fontWeight: "bold", color: "#334155", display: "block", marginBottom: "5px", fontSize: "0.9rem" }}>⚡ Quick preset (optional):</label>
                    <select
                      className="qp-route-select"
                      value={TRANSIT_OPTIONS.includes(day.transit_route) ? day.transit_route : ""}
                      onChange={(e) => {
                        const route = e.target.value;
                        if (!route) return;
                        applyRoute(route);
                      }}
                    >
                      <option value="">{day.transit_route && !TRANSIT_OPTIONS.includes(day.transit_route) ? `Current: ${routeLabel(day.transit_route, startPoint, endPoint)} (built from steps below)` : `-- Pick a ready-made route for Day ${activeDay + 1}, or use the steps below --`}</option>
                      {TRANSIT_OPTIONS.map((route, i) => <option key={i} value={route}>{routeLabel(route, startPoint, endPoint)}</option>)}
                    </select>
                  </div>

                  {row(1, "Starting from", activeDay > 0 && !draft.from && !parsed && prevNight ? `(Day ${activeDay} overnight)` : (parsed && activeDay > 0 && from !== autoFrom ? `(Day ${activeDay} ended in ${prevNight || "?"})` : ""), PICK_FROM, from, (o) => pick({ from: o }))}
                  {row(2, "Going to", "", PICK_TO, to, (o) => pick({ to: o }))}
                  {row(3, "Overnight stay", isDep ? "(not needed on departure day)" : "", PICK_NIGHT, night || (customRoute ? (day.overnight_stay || "") : ""), pickNight, isDep)}
                  {customRoute && <div style={{ fontSize: "0.78rem", color: "#64748b", marginBottom: "10px" }}>Using preset “{day.transit_route}”. Pick From / To above to replace it.</div>}
                </div>
              );
            })()}

            {/* Hotel dropdown */}
            <div style={{ marginBottom: "15px" }}>
              <select
                className="qp-hotel-select"
                value={hotelSelections[activeDay] || ""}
                onChange={(e) => setHotelSelections(prev => ({ ...prev, [activeDay]: e.target.value }))}
              >
                <option value="">-- Choose Hotel --</option>
                {(HOTEL_KB[getHotelGroup(timeline[activeDay].overnight_stay)] || HOTEL_KB["srinagar"]).map((hotel) => (
                  <option key={hotel.id} value={hotel.id}>{hotel.name} — {hotel.place} · B&D Included</option>
                ))}
              </select>
            </div>

            {/* AI writer */}
            <div style={{ background: "#faf5ff", border: "1px solid #e9d5ff", borderRadius: "8px", padding: "10px 12px", marginBottom: "4px" }}>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                <input
                  className="qp-route-select"
                  style={{ flex: 1, minWidth: "200px", maxWidth: "none" }}
                  placeholder="Optional hints, e.g. honeymoon couple, relaxed pace, mention Shikara"
                  maxLength={300}
                  value={aiHints}
                  onChange={(e) => setAiHints(e.target.value)}
                />
                <button
                  type="button"
                  onClick={aiRewriteDay}
                  disabled={!!aiBusy}
                  style={{ padding: "8px 14px", borderRadius: "6px", border: "none", background: "#7c3aed", color: "#fff", fontWeight: "bold", cursor: aiBusy ? "wait" : "pointer", minHeight: "38px", opacity: aiBusy ? 0.7 : 1 }}
                >
                  {aiBusy === "day" ? "Writing…" : "✨ Rewrite day with AI"}
                </button>
              </div>
              {aiError && <div style={{ color: "#b91c1c", fontSize: "0.8rem", marginTop: "6px" }}>{aiError}</div>}
              <div style={{ color: "#7e6a9b", fontSize: "0.72rem", marginTop: "6px" }}>AI text only fills the boxes below. Review it before generating the PDF.</div>
            </div>

            {/* Activity list */}
            <div style={{ display: "flex", flexDirection: "column", gap: "15px", marginTop: "15px" }}>
              {timeline[activeDay].schedule.map((slot, actIdx) => (
                <div key={actIdx} style={{ backgroundColor: "#fff", padding: "clamp(10px, 3vw, 15px)", borderRadius: "6px", border: "1px solid #cbd5e1" }}>
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
                      style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid #c4b5fd", background: "#f5f3ff", color: "#6d28d9", fontWeight: "bold", cursor: aiBusy ? "wait" : "pointer", minHeight: "36px", flexShrink: 0, opacity: aiBusy ? 0.7 : 1 }}
                    >
                      {aiBusy === "act-" + actIdx ? "Writing…" : "✨ Write"}
                    </button>
                  </div>
                  <textarea
                    value={slot.description}
                    onChange={(e) => handleDescriptionChange(activeDay, actIdx, e.target.value)}
                    style={{ width: "100%", padding: "8px", border: "1px solid #cbd5e1", borderRadius: "4px", boxSizing: "border-box", resize: "vertical" }}
                    rows={3}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 5. Hotel Cost Dashboard */}
        <HotelCostDashboard hotelSelections={hotelSelections} timeline={timeline} onTotalChange={(total) => setEditableCost(total)} />

        {/* 6. Hotel Photo Manager */}
        <HotelImageManager />

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

          <div className="qp-hotel-assignments">
            <strong style={{ color: "#0f172a", display: "block", marginBottom: "4px" }}>🏨 Hotel Assignments:</strong>
            {timeline.map((day, idx) => {
              const group  = getHotelGroup(day.overnight_stay);
              const selId  = hotelSelections[idx];
              const hotel  = HOTEL_KB[group]?.find(h => h.id === selId);
              return (
                <div key={idx} style={{ display: "flex", justifyContent: "space-between", gap: "8px" }}>
                  <span style={{ color: "#94a3b8" }}>Day {day.day}:</span>
                  <span style={{ fontWeight: "600", color: hotel ? "#4338ca" : "#94a3b8" }}>{hotel ? hotel.name : "Not assigned"}</span>
                </div>
              );
            })}
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
