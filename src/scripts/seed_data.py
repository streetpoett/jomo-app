<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>City Oasis | 城市綠洲</title>
    
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    
    <style>
        body { margin: 0; padding: 0; font-family: "Microsoft JhengHei", sans-serif; }
        #map { height: 100vh; width: 100%; }
        
        .header-card {
            position: absolute; top: 20px; left: 20px; z-index: 1000;
            background: white; padding: 15px 20px; border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            border-left: 5px solid #2ecc71;
        }

        .legend {
            position: absolute; bottom: 30px; right: 20px; z-index: 1000;
            background: white; padding: 10px; border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            font-size: 0.9rem;
        }
        .dot { height: 10px; width: 10px; display: inline-block; border-radius: 50%; margin-right: 5px; }
    </style>
</head>
<body>

    <div class="header-card">
        <h2 style="margin:0; color: #333;">🏙️ 城市綠洲</h2>
        <p style="margin:5px 0 0 0; color:#666; font-size: 0.9rem;">
            尋找喧囂裡的靜謐角落
        </p>
    </div>

    <div class="legend">
        <div><span class="dot" style="background:#2aad27;"></span>舒適 (Comfortable)</div>
        <div><span class="dot" style="background:#cb8427;"></span>擁擠 (Crowded)</div>
        <div><span class="dot" style="background:#ca2828;"></span>爆滿 (Full)</div>
        <div><span class="dot" style="background:#777;"></span>未知 (Unknown)</div>
    </div>

    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <script>
        // 1. Initialize Map
        var map = L.map('map').setView([25.0339, 121.5644], 14);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);

        // --- Explicit Icon Definitions (Safe Method) ---
        // Defining each icon separately to prevent inheritance issues
        
        var commonSettings = {
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        };

        var greenIcon = new L.Icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
            ...commonSettings
        });

        var goldIcon = new L.Icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-gold.png',
            ...commonSettings
        });

        var redIcon = new L.Icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
            ...commonSettings
        });

        var greyIcon = new L.Icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-grey.png',
            ...commonSettings
        });

        function getCrowdStatus(level) {
            if (level <= 2) return "🟢 舒適";
            if (level <= 4) return "🟠 有點擠";
            if (level >= 5) return "🔴 爆滿";
            return "⚪ 未知";
        }

        function getIcon(level) {
            // Force integer conversion just in case
            var lvl = parseInt(level);
            if (isNaN(lvl) || lvl === 0) return greyIcon;
            if (lvl <= 2) return greenIcon;
            if (lvl <= 4) return goldIcon;
            return redIcon;
        }

        // 2. Fetch Data with Debugging
        fetch('/restaurants')
            .then(response => response.json())
            .then(data => {
                console.log("📡 成功抓到資料:", data);
                
                data.forEach(restaurant => {
                    var chosenIcon = getIcon(restaurant.crowd_level);
                    
                    // Debug: Print to console so we can see what's happening
                    console.log(`🏠 店名: ${restaurant.name}, 擁擠度: ${restaurant.crowd_level}, 顏色圖標:`, chosenIcon);

                    var marker = L.marker([restaurant.latitude, restaurant.longitude], {icon: chosenIcon})
                        .addTo(map);
                    
                    marker.bindPopup(`
                        <div style="font-size: 1.1em; margin-bottom: 5px;">
                            <b>${restaurant.name}</b>
                        </div>
                        <div style="color: #555;">
                            ⭐ 評價: ${restaurant.rating}<br>
                            📊 現況: <b>${getCrowdStatus(restaurant.crowd_level)}</b>
                        </div>
                    `);
                });
            })
            .catch(error => console.error('❌ Error:', error));
    </script>
</body>
</html>