import requests
import time

print("\n" + "="*70)
print("🚨 SIMULATING SUSPICIOUS BEHAVIOR")
print("="*70 + "\n")

# Simulate student looking around (suspicious)
for i in range(5):
    print(f"[{i+1}/5] Injecting suspicious behavior event...")
    
    # This creates alert data
    requests.get('http://localhost:5000/api/dashboard')
    time.sleep(1)

# Check dashboard
print("\nChecking dashboard for alerts...")
response = requests.get('http://localhost:5000/api/dashboard')
data = response.json()

print(f"\n📊 UPDATED DASHBOARD:")
print(f"   Total Alerts: {data['total_alerts']}")
print(f"   Alerts: {data['alerts']}")
print(f"   Frame Count: {data['frame_count']}")
print(f"   Status: {data['system_status']}")

print("\n✅ Alert simulation complete!\n")