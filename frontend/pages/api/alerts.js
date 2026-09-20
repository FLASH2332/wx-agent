let gdacsCache = null;
let gdacsCacheTime = 0;

export default async function handler(req, res) {
  const { lat, lon, country } = req.query;
  
  if (!lat || !lon) {
    return res.status(400).json({ error: "Missing lat/lon" });
  }

  try {
    if (country === "US") {
      const nwsRes = await fetch(`https://api.weather.gov/alerts/active?point=${lat},${lon}`, {
        headers: { "User-Agent": "WeatherBuddy/1.0" }
      });
      if (nwsRes.ok) {
        const data = await nwsRes.json();
        const alerts = (data.features || []).map(f => ({
          event: f.properties.event,
          description: f.properties.headline || f.properties.description,
          severity: f.properties.severity
        }));
        return res.status(200).json({ alerts });
      }
    } else {
      // GDACS XML fetch with 5-minute in-memory cache
      const now = Date.now();
      let xml = null;
      
      if (gdacsCache && (now - gdacsCacheTime < 5 * 60 * 1000)) {
        xml = gdacsCache;
      } else {
        const gdacsRes = await fetch("https://www.gdacs.org/xml/rss.xml");
        if (gdacsRes.ok) {
          xml = await gdacsRes.text();
          gdacsCache = xml;
          gdacsCacheTime = now;
        }
      }
      
      if (xml) {
        // Simple regex parse since we don't have xml2js
        const items = xml.split('<item>').slice(1);
        const alerts = [];
        
        for (const item of items) {
          const latMatch = item.match(/<geo:lat>(.*?)<\/geo:lat>/);
          const lonMatch = item.match(/<geo:long>(.*?)<\/geo:long>/);
          if (latMatch && lonMatch) {
            const itemLat = parseFloat(latMatch[1]);
            const itemLon = parseFloat(lonMatch[1]);
            // Check if within ~5 degrees
            if (Math.abs(parseFloat(lat) - itemLat) < 5 && Math.abs(parseFloat(lon) - itemLon) < 5) {
              const titleMatch = item.match(/<title>(.*?)<\/title>/);
              const descMatch = item.match(/<description>(.*?)<\/description>/);
              alerts.push({
                event: titleMatch ? titleMatch[1].replace('<![CDATA[', '').replace(']]>', '') : "Global Alert",
                description: descMatch ? descMatch[1].replace('<![CDATA[', '').replace(']]>', '') : "",
                severity: "Warning"
              });
            }
          }
        }
        return res.status(200).json({ alerts });
      }
    }
    
    return res.status(200).json({ alerts: [] });
  } catch (error) {
    console.error("Alerts API error:", error);
    return res.status(500).json({ error: "Failed to fetch alerts" });
  }
}
