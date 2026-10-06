"""alert-handler Lambda — runs on a daily EventBridge schedule.

Checks NWS (US) or GDACS (global) for active weather alerts at ALERT_LOCATION
and publishes a summary to the SNS topic if anything is found.
"""

import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import boto3

OWM_API_KEY = os.environ["OWM_API_KEY"]
ALERT_LOCATION = os.environ.get("ALERT_LOCATION", "Chennai, IN")
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

sns = boto3.client("sns", region_name=AWS_REGION)


def _geocode(location):
    url = "https://api.openweathermap.org/geo/1.0/direct"
    qs = urllib.parse.urlencode({"q": location, "limit": 1, "appid": OWM_API_KEY})
    with urllib.request.urlopen(f"{url}?{qs}", timeout=10) as r:
        data = json.loads(r.read())
    if not data:
        return None
    return data[0]["lat"], data[0]["lon"], data[0].get("country", "")


def _fetch_nws_alerts(lat, lon):
    url = f"https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}"
    req = urllib.request.Request(url, headers={"User-Agent": "WeatherBuddy/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        alerts = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            alerts.append({
                "event": props.get("event", "Alert"),
                "severity": props.get("severity", "Unknown"),
                "description": (props.get("description") or "")[:200],
            })
        return alerts
    except Exception:
        return []


def _fetch_gdacs_alerts(lat, lon):
    try:
        with urllib.request.urlopen(
            "https://www.gdacs.org/xml/rss.xml", timeout=10
        ) as r:
            root = ET.fromstring(r.read())
        alerts = []
        for item in root.findall(".//item")[:5]:
            title = item.findtext("title", "")
            desc = item.findtext("description", "")[:200]
            alerts.append({"event": title, "severity": "Unknown", "description": desc})
        return alerts
    except Exception:
        return []


def handler(event, context=None):
    geo = _geocode(ALERT_LOCATION)
    if not geo:
        print(f"Could not geocode location: {ALERT_LOCATION}")
        return

    lat, lon, country = geo
    alerts = _fetch_nws_alerts(lat, lon) if country == "US" else _fetch_gdacs_alerts(lat, lon)

    if not alerts:
        print(f"No active alerts for {ALERT_LOCATION}")
        return

    lines = [f"Weather Buddy — Alert Report for {ALERT_LOCATION}\n"]
    for a in alerts[:3]:
        lines.append(f"• {a['event']} ({a['severity']})")
        if a["description"]:
            lines.append(f"  {a['description']}")
        lines.append("")

    message = "\n".join(lines)
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"⚠️ Weather Alert: {ALERT_LOCATION}",
        Message=message,
    )
    print(f"Published {len(alerts)} alert(s) for {ALERT_LOCATION}")
