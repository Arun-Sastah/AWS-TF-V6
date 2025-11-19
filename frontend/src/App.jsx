import React, { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL;
console.log("API_URL =", API_URL);

function App() {
  const [status, setStatus] = useState("");
  const [user, setUser] = useState("");
  const [device, setDevice] = useState("");
  const [loading, setLoading] = useState(false);

  const callAPI = async (endpoint) => {
    if (!user || !device) {
      setStatus("⚠️ Enter both User + Device ID");
      return;
    }

    setLoading(true);
    setStatus(endpoint === "create-server" ? "Creating server…" : "Destroying server…");

    try {
      const res = await fetch(`${API_URL}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user,
          device_id: device,
          instance_name: `${user}-${device}`,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        setStatus(`✔ ${data.message}`);
      } else {
        setStatus(`❌ ${data.detail || "Unknown error"}`);
      }
    } catch (e) {
      setStatus(`⚠ ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      textAlign: "center", 
      padding: "40px", 
      fontFamily: "Arial, sans-serif" 
    }}>
      
      <h1 style={{ marginBottom: "20px" }}>AWS Server Manager</h1>

      {/* Input Section */}
      <div style={{ marginBottom: "20px" }}>
        <input
          placeholder="User"
          value={user}
          onChange={(e) => setUser(e.target.value)}
          style={{ padding: "8px", marginRight: "10px" }}
        />
        <input
          placeholder="Device ID"
          value={device}
          onChange={(e) => setDevice(e.target.value)}
          style={{ padding: "8px" }}
        />
      </div>

      {/* Buttons */}
      <div style={{ marginBottom: "20px" }}>
        <button
          onClick={() => callAPI("create-server")}
          disabled={loading}
          style={{
            padding: "12px 24px",
            marginRight: "10px",
            backgroundColor: "#00a65a",
            color: "white",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
          }}
        >
          Create Server
        </button>

        <button
          onClick={() => callAPI("destroy-server")}
          disabled={loading}
          style={{
            padding: "12px 24px",
            backgroundColor: "#d9534f",
            color: "white",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
          }}
        >
          Destroy Server
        </button>
      </div>

      {/* Status */}
      <div style={{
        marginTop: "20px",
        fontSize: "1.2em",
        fontWeight: "bold"
      }}>
        {loading ? "⏳ Working…" : status}
      </div>
    </div>
  );
}

export default App;
