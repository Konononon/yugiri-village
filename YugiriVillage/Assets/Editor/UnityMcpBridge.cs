using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Yugiri.EditorMCP
{
    [InitializeOnLoad]
    public static class UnityMcpBridge
    {
        public const int Port = 9877;
        private static TcpListener _listener;
        private static Thread _acceptThread;
        private static volatile bool _running;

        private class PendingRequest
        {
            public string RawJson;
            public ManualResetEventSlim Done = new ManualResetEventSlim(false);
            public string ResponseJson;
        }

        private static readonly ConcurrentQueue<PendingRequest> _queue = new ConcurrentQueue<PendingRequest>();
        private static readonly List<string> _logs = new List<string>();
        private static readonly object _logLock = new object();

        static UnityMcpBridge()
        {
            Application.logMessageReceivedThreaded -= OnLogMessage;
            Application.logMessageReceivedThreaded += OnLogMessage;

            AssemblyReloadEvents.beforeAssemblyReload -= StopServer;
            AssemblyReloadEvents.beforeAssemblyReload += StopServer;

            EditorApplication.quitting -= StopServer;
            EditorApplication.quitting += StopServer;

            EditorApplication.update -= ProcessQueue;
            EditorApplication.update += ProcessQueue;

            StartServer();
        }

        private static void OnLogMessage(string condition, string stackTrace, LogType type)
        {
            lock (_logLock)
            {
                if (_logs.Count > 300)
                {
                    _logs.RemoveAt(0);
                }
                _logs.Add($"[{type}] {condition}");
            }
        }

        [MenuItem("Window/MCP for Unity/Restart Server (Port 9877)")]
        public static void RestartServerMenu()
        {
            StopServer();
            StartServer();
            Debug.Log($"[UnityMCP] Server listening on 127.0.0.1:{Port}");
        }

        public static void StartServer()
        {
            if (_running) return;
            try
            {
                _listener = new TcpListener(IPAddress.Loopback, Port);
                _listener.Server.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
                _listener.Start();
                _running = true;

                _acceptThread = new Thread(AcceptLoop)
                {
                    IsBackground = true,
                    Name = "UnityMCP_AcceptThread"
                };
                _acceptThread.Start();
                Debug.Log($"[UnityMCP] Bridge automatically started on 127.0.0.1:{Port}");
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityMCP] Could not bind port {Port}: {ex.Message}");
            }
        }

        public static void StopServer()
        {
            _running = false;
            try
            {
                _listener?.Stop();
            }
            catch { }
            _listener = null;
        }

        private static void AcceptLoop()
        {
            while (_running && _listener != null)
            {
                try
                {
                    TcpClient client = _listener.AcceptTcpClient();
                    ThreadPool.QueueUserWorkItem(_ => HandleClient(client));
                }
                catch
                {
                    if (!_running) break;
                }
            }
        }

        private static void HandleClient(TcpClient client)
        {
            using (client)
            {
                try
                {
                    client.ReceiveTimeout = 180000;
                    client.SendTimeout = 180000;
                    using (NetworkStream stream = client.GetStream())
                    using (StreamReader reader = new StreamReader(stream, Encoding.UTF8))
                    {
                        string line = reader.ReadLine();
                        if (string.IsNullOrEmpty(line)) return;

                        PendingRequest req = new PendingRequest { RawJson = line };
                        _queue.Enqueue(req);

                        if (!req.Done.Wait(175000))
                        {
                            req.ResponseJson = "{\"status\":\"error\",\"message\":\"Timeout waiting for Unity Editor main thread\"}";
                        }

                        byte[] outBytes = Encoding.UTF8.GetBytes((req.ResponseJson ?? "{\"status\":\"error\"}") + "\n");
                        stream.Write(outBytes, 0, outBytes.Length);
                        stream.Flush();
                    }
                }
                catch (Exception ex)
                {
                    try
                    {
                        if (client.Connected)
                        {
                            string err = $"{{\"status\":\"error\",\"message\":\"{EscapeJson(ex.Message)}\"}}\n";
                            byte[] b = Encoding.UTF8.GetBytes(err);
                            client.GetStream().Write(b, 0, b.Length);
                        }
                    }
                    catch { }
                }
            }
        }

        private static void ProcessQueue()
        {
            int processed = 0;
            while (processed < 8 && _queue.TryDequeue(out PendingRequest req))
            {
                processed++;
                try
                {
                    req.ResponseJson = ExecuteCommandJson(req.RawJson);
                }
                catch (Exception ex)
                {
                    req.ResponseJson = $"{{\"status\":\"error\",\"message\":\"{EscapeJson(ex.ToString())}\"}}";
                }
                finally
                {
                    req.Done.Set();
                }
            }
        }

        private static string ExecuteCommandJson(string rawJson)
        {
            string cmdType = ExtractJsonString(rawJson, "type");
            if (string.IsNullOrEmpty(cmdType))
            {
                return "{\"status\":\"error\",\"message\":\"Missing command type\"}";
            }

            switch (cmdType)
            {
                case "ping":
                case "get_editor_state":
                    return HandleGetEditorState();
                case "get_scene_hierarchy":
                    return HandleGetSceneHierarchy(rawJson);
                case "get_object_info":
                    return HandleGetObjectInfo(rawJson);
                case "manage_gameobject":
                    return HandleManageGameObject(rawJson);
                case "refresh_assets":
                    return HandleRefreshAssets();
                case "execute_menu_item":
                    return HandleExecuteMenuItem(rawJson);
                case "invoke_static_method":
                    return HandleInvokeStaticMethod(rawJson);
                case "capture_screenshot":
                    return HandleCaptureScreenshot(rawJson);
                case "get_console_logs":
                    return HandleGetConsoleLogs(rawJson);
                case "save_scene":
                    return HandleSaveScene(rawJson);
                default:
                    return $"{{\"status\":\"error\",\"message\":\"Unknown command: {EscapeJson(cmdType)}\"}}";
            }
        }

        private static string HandleGetEditorState()
        {
            Scene scene = SceneManager.GetActiveScene();
            GameObject[] roots = scene.IsValid() ? scene.GetRootGameObjects() : new GameObject[0];
            int totalObjects = UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsSortMode.None).Length;
            int totalLights = UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None).Length;
            int totalRenderers = UnityEngine.Object.FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None).Length;

            StringBuilder sb = new StringBuilder();
            sb.Append("{\"status\":\"success\",\"result\":{");
            sb.Append($"\"unity_version\":\"{EscapeJson(Application.unityVersion)}\",");
            sb.Append($"\"project_path\":\"{EscapeJson(Application.dataPath)}\",");
            sb.Append($"\"scene_name\":\"{EscapeJson(scene.name)}\",");
            sb.Append($"\"scene_path\":\"{EscapeJson(scene.path)}\",");
            sb.Append($"\"root_count\":{roots.Length},");
            sb.Append($"\"total_transforms\":{totalObjects},");
            sb.Append($"\"total_mesh_renderers\":{totalRenderers},");
            sb.Append($"\"total_lights\":{totalLights},");
            sb.Append($"\"is_compiling\":{(EditorApplication.isCompiling ? "true" : "false")},");
            sb.Append($"\"is_playing\":{(EditorApplication.isPlaying ? "true" : "false")},");
            sb.Append($"\"fog_enabled\":{(RenderSettings.fog ? "true" : "false")},");
            sb.Append($"\"fog_density\":{RenderSettings.fogDensity.ToString(CultureInfo.InvariantCulture)}");
            sb.Append("}}");
            return sb.ToString();
        }

        private static string HandleGetSceneHierarchy(string rawJson)
        {
            Scene scene = SceneManager.GetActiveScene();
            GameObject[] roots = scene.IsValid() ? scene.GetRootGameObjects() : new GameObject[0];

            StringBuilder sb = new StringBuilder();
            sb.Append("{\"status\":\"success\",\"result\":{\"scene\":\"");
            sb.Append(EscapeJson(scene.name));
            sb.Append("\",\"roots\":[");
            for (int i = 0; i < roots.Length; i++)
            {
                if (i > 0) sb.Append(",");
                GameObject go = roots[i];
                Vector3 p = go.transform.position;
                sb.Append("{");
                sb.Append($"\"name\":\"{EscapeJson(go.name)}\",");
                sb.Append($"\"active\":{(go.activeInHierarchy ? "true" : "false")},");
                sb.Append($"\"children\":{go.transform.childCount},");
                sb.Append(string.Format(CultureInfo.InvariantCulture, "\"position\":[{0:F2},{1:F2},{2:F2}]", p.x, p.y, p.z));
                sb.Append("}");
            }
            sb.Append("]}}");
            return sb.ToString();
        }

        private static string HandleGetObjectInfo(string rawJson)
        {
            string name = ExtractJsonString(rawJson, "name");
            GameObject go = FindGameObject(name);
            if (go == null)
            {
                return $"{{\"status\":\"error\",\"message\":\"GameObject '{EscapeJson(name)}' not found\"}}";
            }

            Vector3 p = go.transform.position;
            Vector3 r = go.transform.eulerAngles;
            Vector3 s = go.transform.localScale;
            Component[] comps = go.GetComponents<Component>();
            MeshFilter mf = go.GetComponent<MeshFilter>();
            MeshRenderer mr = go.GetComponent<MeshRenderer>();

            int verts = (mf != null && mf.sharedMesh != null) ? mf.sharedMesh.vertexCount : 0;
            int tris = (mf != null && mf.sharedMesh != null) ? mf.sharedMesh.triangles.Length / 3 : 0;

            StringBuilder sb = new StringBuilder();
            sb.Append("{\"status\":\"success\",\"result\":{");
            sb.Append($"\"name\":\"{EscapeJson(go.name)}\",");
            sb.Append(string.Format(CultureInfo.InvariantCulture, "\"position\":[{0:F3},{1:F3},{2:F3}],", p.x, p.y, p.z));
            sb.Append(string.Format(CultureInfo.InvariantCulture, "\"rotation\":[{0:F2},{1:F2},{2:F2}],", r.x, r.y, r.z));
            sb.Append(string.Format(CultureInfo.InvariantCulture, "\"scale\":[{0:F3},{1:F3},{2:F3}],", s.x, s.y, s.z));
            sb.Append($"\"vertex_count\":{verts},");
            sb.Append($"\"triangle_count\":{tris},");
            sb.Append($"\"child_count\":{go.transform.childCount},");
            sb.Append("\"components\":[");
            for (int i = 0; i < comps.Length; i++)
            {
                if (i > 0) sb.Append(",");
                sb.Append($"\"{EscapeJson(comps[i] != null ? comps[i].GetType().Name : "Missing")}\"");
            }
            sb.Append("],\"materials\":[");
            if (mr != null && mr.sharedMaterials != null)
            {
                for (int i = 0; i < mr.sharedMaterials.Length; i++)
                {
                    if (i > 0) sb.Append(",");
                    Material m = mr.sharedMaterials[i];
                    sb.Append($"\"{EscapeJson(m != null ? m.name + " (" + m.shader.name + ")" : "null")}\"");
                }
            }
            sb.Append("]}}");
            return sb.ToString();
        }

        private static string HandleManageGameObject(string rawJson)
        {
            string action = ExtractJsonString(rawJson, "action");
            string name = ExtractJsonString(rawJson, "name");
            string parentName = ExtractJsonString(rawJson, "parent");
            string primitive = ExtractJsonString(rawJson, "primitive_type");

            GameObject go = FindGameObject(name);
            if (action == "delete")
            {
                if (go == null) return $"{{\"status\":\"error\",\"message\":\"Object '{EscapeJson(name)}' not found\"}}";
                UnityEngine.Object.DestroyImmediate(go);
                return $"{{\"status\":\"success\",\"result\":{{\"deleted\":\"{EscapeJson(name)}\"}}}}";
            }

            if (action == "create" || go == null)
            {
                if (!string.IsNullOrEmpty(primitive) && Enum.TryParse(primitive, true, out PrimitiveType pt))
                {
                    go = GameObject.CreatePrimitive(pt);
                    go.name = name;
                }
                else
                {
                    go = new GameObject(name);
                }
            }

            if (!string.IsNullOrEmpty(parentName))
            {
                GameObject parentGo = FindGameObject(parentName);
                if (parentGo != null) go.transform.SetParent(parentGo.transform, false);
            }

            if (TryExtractFloatArray(rawJson, "position", out float[] pos) && pos.Length == 3)
                go.transform.position = new Vector3(pos[0], pos[1], pos[2]);
            if (TryExtractFloatArray(rawJson, "rotation", out float[] rot) && rot.Length == 3)
                go.transform.eulerAngles = new Vector3(rot[0], rot[1], rot[2]);
            if (TryExtractFloatArray(rawJson, "scale", out float[] scl) && scl.Length == 3)
                go.transform.localScale = new Vector3(scl[0], scl[1], scl[2]);

            EditorSceneManager.MarkSceneDirty(SceneManager.GetActiveScene());
            return $"{{\"status\":\"success\",\"result\":{{\"name\":\"{EscapeJson(go.name)}\"}}}}";
        }

        private static string HandleRefreshAssets()
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            return HandleGetEditorState();
        }

        private static string HandleExecuteMenuItem(string rawJson)
        {
            string menuPath = ExtractJsonString(rawJson, "menu_path");
            bool ok = EditorApplication.ExecuteMenuItem(menuPath);
            return $"{{\"status\":\"{(ok ? "success" : "error")}\",\"result\":{{\"menu_path\":\"{EscapeJson(menuPath)}\",\"executed\":{(ok ? "true" : "false")}}}}}";
        }

        private static string HandleInvokeStaticMethod(string rawJson)
        {
            string typeName = ExtractJsonString(rawJson, "type_name");
            string methodName = ExtractJsonString(rawJson, "method_name");
            string arg = ExtractJsonString(rawJson, "arg");

            Type foundType = null;
            foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                foreach (Type t in asm.GetTypes())
                {
                    if (t.Name == typeName || t.FullName == typeName)
                    {
                        foundType = t;
                        break;
                    }
                }
                if (foundType != null) break;
            }

            if (foundType == null)
            {
                return $"{{\"status\":\"error\",\"message\":\"Type '{EscapeJson(typeName)}' not found\"}}";
            }

            MethodInfo mi = foundType.GetMethod(methodName, BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
            if (mi == null)
            {
                return $"{{\"status\":\"error\",\"message\":\"Method '{EscapeJson(methodName)}' not found on '{EscapeJson(typeName)}'\"}}";
            }

            ParameterInfo[] pars = mi.GetParameters();
            object ret;
            if (pars.Length == 0)
                ret = mi.Invoke(null, null);
            else
                ret = mi.Invoke(null, new object[] { arg });

            string retStr = ret != null ? ret.ToString() : "OK";
            return $"{{\"status\":\"success\",\"result\":{{\"return\":\"{EscapeJson(retStr)}\"}}}}";
        }

        private static string HandleCaptureScreenshot(string rawJson)
        {
            string outputPath = ExtractJsonString(rawJson, "output_path");
            if (string.IsNullOrEmpty(outputPath))
            {
                outputPath = Path.Combine(Directory.GetParent(Application.dataPath).FullName, "screenshot.png");
            }
            int width = ExtractJsonInt(rawJson, "width", 1920);
            int height = ExtractJsonInt(rawJson, "height", 1080);
            float fov = ExtractJsonFloat(rawJson, "fov", 60f);

            Camera cam = Camera.main;
            if (cam == null)
            {
                Camera[] allCams = UnityEngine.Object.FindObjectsByType<Camera>(FindObjectsSortMode.None);
                if (allCams.Length > 0) cam = allCams[0];
            }
            if (cam == null)
            {
                return "{\"status\":\"error\",\"message\":\"No Camera found in scene\"}";
            }

            Vector3 origPos = cam.transform.position;
            Quaternion origRot = cam.transform.rotation;
            float origFov = cam.fieldOfView;
            bool origHdr = cam.allowHDR;

            try
            {
                if (TryExtractFloatArray(rawJson, "camera_position", out float[] cpos) && cpos != null && cpos.Length == 3)
                    cam.transform.position = new Vector3(cpos[0], cpos[1], cpos[2]);
                if (TryExtractFloatArray(rawJson, "camera_euler", out float[] ceul) && ceul != null && ceul.Length == 3)
                    cam.transform.eulerAngles = new Vector3(ceul[0], ceul[1], ceul[2]);
                if (fov > 1f) cam.fieldOfView = fov;
                cam.allowHDR = true;

                // Ensure any reflection probes or post-fx are updated
                RenderTexture rt = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32);
                rt.antiAliasing = 4;
                RenderTexture prevTarget = cam.targetTexture;
                RenderTexture prevActive = RenderTexture.active;

                cam.targetTexture = rt;
                cam.Render();

                RenderTexture.active = rt;
                Texture2D tex = new Texture2D(width, height, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                tex.Apply();

                cam.targetTexture = prevTarget;
                RenderTexture.active = prevActive;

                Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath)));
                byte[] png = tex.EncodeToPNG();
                File.WriteAllBytes(outputPath, png);

                UnityEngine.Object.DestroyImmediate(tex);
                UnityEngine.Object.DestroyImmediate(rt);

                return $"{{\"status\":\"success\",\"result\":{{\"output_path\":\"{EscapeJson(outputPath)}\",\"width\":{width},\"height\":{height},\"bytes\":{png.Length}}}}}";
            }
            finally
            {
                cam.transform.position = origPos;
                cam.transform.rotation = origRot;
                cam.fieldOfView = origFov;
                cam.allowHDR = origHdr;
            }
        }

        private static string HandleGetConsoleLogs(string rawJson)
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("{\"status\":\"success\",\"result\":{\"logs\":[");
            lock (_logLock)
            {
                int start = Mathf.Max(0, _logs.Count - 50);
                for (int i = start; i < _logs.Count; i++)
                {
                    if (i > start) sb.Append(",");
                    sb.Append($"\"{EscapeJson(_logs[i])}\"");
                }
                if (rawJson.Contains("\"clear\": true") || rawJson.Contains("\"clear\":true"))
                {
                    _logs.Clear();
                }
            }
            sb.Append("]}}");
            return sb.ToString();
        }

        private static string HandleSaveScene(string rawJson)
        {
            Scene scene = SceneManager.GetActiveScene();
            string scenePath = ExtractJsonString(rawJson, "scene_path");
            bool ok;
            if (!string.IsNullOrEmpty(scenePath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(scenePath)));
                ok = EditorSceneManager.SaveScene(scene, scenePath);
            }
            else
            {
                ok = EditorSceneManager.SaveScene(scene);
            }
            AssetDatabase.SaveAssets();
            return $"{{\"status\":\"{(ok ? "success" : "error")}\",\"result\":{{\"scene_path\":\"{EscapeJson(scene.path)}\"}}}}";
        }

        private static GameObject FindGameObject(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            GameObject found = GameObject.Find(name);
            if (found != null) return found;
            foreach (Transform t in UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                if (t.name == name) return t.gameObject;
            }
            return null;
        }

        private static string ExtractJsonString(string json, string key)
        {
            Match m = Regex.Match(json, $"\"{Regex.Escape(key)}\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"");
            if (!m.Success) return "";
            return Regex.Unescape(m.Groups[1].Value);
        }

        private static int ExtractJsonInt(string json, string key, int defaultVal)
        {
            Match m = Regex.Match(json, $"\"{Regex.Escape(key)}\"\\s*:\\s*(-?\\d+)");
            if (!m.Success) return defaultVal;
            return int.TryParse(m.Groups[1].Value, out int v) ? v : defaultVal;
        }

        private static float ExtractJsonFloat(string json, string key, float defaultVal)
        {
            Match m = Regex.Match(json, $"\"{Regex.Escape(key)}\"\\s*:\\s*(-?\\d+(?:\\.\\d+)?)");
            if (!m.Success) return defaultVal;
            return float.TryParse(m.Groups[1].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out float v) ? v : defaultVal;
        }

        private static bool TryExtractFloatArray(string json, string key, out float[] values)
        {
            values = null;
            Match m = Regex.Match(json, $"\"{Regex.Escape(key)}\"\\s*:\\s*\\[([^\\]]+)\\]");
            if (!m.Success) return false;
            string[] parts = m.Groups[1].Value.Split(',');
            List<float> list = new List<float>();
            foreach (string p in parts)
            {
                if (float.TryParse(p.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out float f))
                    list.Add(f);
            }
            values = list.ToArray();
            return values.Length > 0;
        }

        private static string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", "\\r").Replace("\n", "\\n");
        }
    }
}
