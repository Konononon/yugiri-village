using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using Yugiri.Gameplay;

public static class YugiriSceneBuilder
{
    private static readonly string[] MatKeys = new string[]
    {
        "WetAsphalt",
        "StonePaving",
        "ConcreteWall",
        "DarkWood",
        "AgedPlaster",
        "KawaraTile",
        "RustedMetal",
        "ShojiWindow",
        "ShojiWindowEerie",
        "ToriiVermilion",
        "MossyGranite",
        "VendingMachineFront",
        "ShopShutterSign",
        "UtilityConcrete",
        "ACUnitMetal",
        "ShrineWoodOrnament",
        "FoliageBark",
        "PropsAtlas",
        "FoliageLeafCutout"
    };

    private static readonly Dictionary<string, Material> _materials = new Dictionary<string, Material>();

    [MenuItem("Yugiri/Build Complete Village Scene")]
    public static string BuildCompleteGame()
    {
        Directory.CreateDirectory("Assets/Materials");
        Directory.CreateDirectory("Assets/Scenes");

        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);

        ConfigureTextures();
        BuildMaterials();
        ConfigureModels();
        BuildScene();

        AssetDatabase.SaveAssets();
        return "Yugiri Village Horror Scene built and saved successfully.";
    }

    private static void ConfigureTextures()
    {
        string[] guids = AssetDatabase.FindAssets("t:Texture2D", new[] { "Assets/Textures" });
        foreach (string guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            TextureImporter ti = AssetImporter.GetAtPath(path) as TextureImporter;
            if (ti == null) continue;

            bool changed = false;
            bool isNormal = path.EndsWith("_Normal.png", StringComparison.OrdinalIgnoreCase);
            bool isLinear = isNormal || path.EndsWith("_MetallicSmoothness.png", StringComparison.OrdinalIgnoreCase) || path.EndsWith("_AO.png", StringComparison.OrdinalIgnoreCase);
            bool isCutoutAlbedo = path.IndexOf("FoliageLeafCutout_Albedo", StringComparison.OrdinalIgnoreCase) >= 0;

            if (isNormal && ti.textureType != TextureImporterType.NormalMap)
            {
                ti.textureType = TextureImporterType.NormalMap;
                changed = true;
            }
            if (!isNormal && ti.sRGBTexture == isLinear)
            {
                ti.sRGBTexture = !isLinear;
                changed = true;
            }
            if (isCutoutAlbedo && !ti.alphaIsTransparency)
            {
                ti.alphaSource = TextureImporterAlphaSource.FromInput;
                ti.alphaIsTransparency = true;
                changed = true;
            }
            if (ti.anisoLevel != 8)
            {
                ti.anisoLevel = 8;
                changed = true;
            }
            if (ti.maxTextureSize != 2048)
            {
                ti.maxTextureSize = 2048;
                changed = true;
            }
            if (changed)
            {
                ti.SaveAndReimport();
            }
        }
    }

    private static void BuildMaterials()
    {
        _materials.Clear();
        Shader wetShader = Shader.Find("Custom/YugiriWetSurface");
        if (wetShader == null) wetShader = Shader.Find("Standard");
        Shader foliageCutoutShader = Shader.Find("Custom/YugiriFoliageCutout");
        if (foliageCutoutShader == null) foliageCutoutShader = wetShader;

        foreach (string key in MatKeys)
        {
            string matPath = $"Assets/Materials/Mat_{key}.mat";
            Material mat = AssetDatabase.LoadAssetAtPath<Material>(matPath);
            Shader targetShader = (key == "FoliageLeafCutout") ? foliageCutoutShader : wetShader;
            if (mat == null)
            {
                mat = new Material(targetShader);
                AssetDatabase.CreateAsset(mat, matPath);
            }
            else
            {
                mat.shader = targetShader;
            }

            Texture2D alb = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Textures/{key}_Albedo.png");
            Texture2D nrm = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Textures/{key}_Normal.png");
            Texture2D ms = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Textures/{key}_MetallicSmoothness.png");
            Texture2D ao = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Textures/{key}_AO.png");
            Texture2D em = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Textures/{key}_Emission.png");

            mat.SetTexture("_MainTex", alb);
            mat.SetColor("_Color", Color.white);

            if (key == "FoliageLeafCutout")
            {
                mat.SetFloat("_Cutoff", 0.35f);
                mat.SetTexture("_BumpMap", nrm);
                mat.SetFloat("_BumpScale", 1.35f);
                mat.SetTexture("_MetallicGlossMap", ms);
                mat.SetFloat("_Glossiness", 0.84f);
                mat.SetFloat("_Wetness", 0.88f);
                mat.SetFloat("_WindStrength", 0.016f);
                EditorUtility.SetDirty(mat);
                _materials[key] = mat;
                continue;
            }

            if (nrm != null)
            {
                mat.EnableKeyword("_NORMALMAP");
                mat.SetTexture("_BumpMap", nrm);
                float bumpScale = 0.78f;
                if (key == "KawaraTile" || key == "StonePaving" || key == "ConcreteWall" || key == "WetAsphalt") bumpScale = 0.92f;
                else if (key == "DarkWood" || key == "ToriiVermilion" || key == "ShrineWoodOrnament") bumpScale = 0.56f;
                else if (key == "ShojiWindow" || key == "ShojiWindowEerie" || key == "ShopShutterSign") bumpScale = 0.42f;
                mat.SetFloat("_BumpScale", bumpScale);
            }

            if (ms != null)
            {
                mat.EnableKeyword("_METALLICGLOSSMAP");
                mat.SetTexture("_MetallicGlossMap", ms);
                mat.SetFloat("_GlossMapScale", 1.0f);
                mat.SetInt("_SmoothnessTextureChannel", 0);
            }

            if (ao != null)
            {
                mat.SetTexture("_OcclusionMap", ao);
                mat.SetFloat("_OcclusionStrength", 0.85f);
            }

            // Configure procedural rain wetness, puddle coverage, and raindrop ripples
            bool isGroundOrRoof = (key == "WetAsphalt" || key == "StonePaving" || key == "MossyGranite" || key == "KawaraTile");
            bool isEmissiveWindow = (key == "ShojiWindow" || key == "ShojiWindowEerie" || key == "VendingMachineFront");
            mat.SetFloat("_WetLevel", isEmissiveWindow ? 0.15f : (isGroundOrRoof ? 0.96f : 0.78f));
            mat.SetFloat("_PuddleAmount", key == "WetAsphalt" ? 0.82f : (isGroundOrRoof ? 0.62f : 0.25f));
            mat.SetFloat("_RippleStrength", key == "WetAsphalt" ? 0.52f : (isGroundOrRoof ? 0.38f : 0.12f));

            if (key == "WetAsphalt") mat.SetColor("_Color", new Color(0.68f, 0.72f, 0.78f));
            else if (key == "FoliageBark") mat.SetColor("_Color", new Color(0.75f, 0.82f, 0.76f));
            else mat.SetColor("_Color", Color.white);

            if (em != null)
            {
                mat.EnableKeyword("_EMISSION");
                mat.SetTexture("_EmissionMap", em);
                Color emCol = Color.white;
                if (key == "VendingMachineFront") emCol = new Color(0.82f, 0.94f, 1.08f);
                else if (key == "ShojiWindow") emCol = new Color(0.95f, 0.62f, 0.28f);
                else if (key == "ShojiWindowEerie") emCol = new Color(0.48f, 0.96f, 0.82f);
                else if (key == "ShopShutterSign") emCol = new Color(0.95f, 0.82f, 0.62f);
                mat.SetColor("_EmissionColor", emCol);
                mat.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
            }
            else
            {
                mat.DisableKeyword("_EMISSION");
                mat.SetColor("_EmissionColor", Color.black);
            }

            EditorUtility.SetDirty(mat);
            _materials[key] = mat;
        }
    }

    private static void ConfigureModels()
    {
        string[] guids = AssetDatabase.FindAssets("t:Model", new[] { "Assets/Models" });
        foreach (string guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            ModelImporter mi = AssetImporter.GetAtPath(path) as ModelImporter;
            if (mi == null) continue;

            bool changed = false;
            if (!mi.addCollider)
            {
                mi.addCollider = true;
                changed = true;
            }
            if (!mi.useFileScale)
            {
                mi.useFileScale = true;
                changed = true;
            }
            if (changed)
            {
                mi.SaveAndReimport();
            }
        }
    }

    private static GameObject SpawnModel(string modelName, string instanceName, Transform parent, Vector3 pos, Vector3 euler, Vector3 scale)
    {
        GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Models/{modelName}.fbx");
        if (prefab == null)
        {
            Debug.LogWarning($"Model not found: Assets/Models/{modelName}.fbx");
            return null;
        }

        GameObject wrapper = new GameObject(instanceName);
        if (parent != null) wrapper.transform.SetParent(parent, false);
        wrapper.transform.position = pos;
        wrapper.transform.eulerAngles = euler;
        wrapper.transform.localScale = scale;

        GameObject go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        go.name = modelName + "_Mesh";
        go.transform.SetParent(wrapper.transform, false);

        // Bind our custom PBR materials to all MeshRenderers (match longest key so ShojiWindowEerie beats ShojiWindow)
        foreach (MeshRenderer mr in go.GetComponentsInChildren<MeshRenderer>(true))
        {
            Material[] shared = mr.sharedMaterials;
            for (int i = 0; i < shared.Length; i++)
            {
                if (shared[i] != null)
                {
                    string mName = shared[i].name;
                    Material bestMat = null;
                    int bestLen = -1;
                    foreach (var kv in _materials)
                    {
                        if (mName.IndexOf(kv.Key, StringComparison.OrdinalIgnoreCase) >= 0 && kv.Key.Length > bestLen)
                        {
                            bestMat = kv.Value;
                            bestLen = kv.Key.Length;
                        }
                    }
                    if (bestMat != null) shared[i] = bestMat;
                }
            }
            mr.sharedMaterials = shared;
            mr.shadowCastingMode = ShadowCastingMode.On;
            mr.receiveShadows = true;
        }

        if (go.GetComponentInChildren<Collider>() == null)
        {
            foreach (MeshFilter mf in go.GetComponentsInChildren<MeshFilter>(true))
            {
                if (mf.sharedMesh != null && mf.gameObject.GetComponent<Collider>() == null)
                {
                    mf.gameObject.AddComponent<MeshCollider>();
                }
            }
        }

        return wrapper;
    }

    private static Light CreateLight(string name, Transform parent, LightType type, Vector3 pos, Vector3 euler, Color color, float intensity, float range, float spotAngle = 60f, bool shadows = true)
    {
        GameObject go = new GameObject(name);
        if (parent != null) go.transform.SetParent(parent, false);
        go.transform.position = pos;
        go.transform.eulerAngles = euler;

        Light l = go.AddComponent<Light>();
        l.type = type;
        l.color = color;
        l.intensity = intensity;
        l.range = range;
        l.spotAngle = spotAngle;
        l.shadows = shadows ? LightShadows.Soft : LightShadows.None;
        l.shadowStrength = 0.88f;
        l.renderMode = LightRenderMode.ForcePixel;
        return l;
    }

    private static void AttachInteractable(GameObject target, string titleJp, string dialogue, AudioClip sfx = null, AudioClip stinger = null, bool shrineEvent = false)
    {
        if (target == null) return;
        YugiriInteractable inter = target.GetComponent<YugiriInteractable>();
        if (inter == null) inter = target.AddComponent<YugiriInteractable>();
        inter.titleJp = titleJp;
        inter.inspectDialogue = dialogue;
        inter.interactSfx = sfx;
        inter.horrorStingerSfx = stinger;
        inter.triggersShrineEvent = shrineEvent;
    }

    private static void BuildScene()
    {
        Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // Configure QualitySettings for maximum graphical fidelity
        QualitySettings.pixelLightCount = 16;
        QualitySettings.shadows = ShadowQuality.All;
        QualitySettings.shadowResolution = ShadowResolution.VeryHigh;
        QualitySettings.shadowDistance = 55f;
        QualitySettings.antiAliasing = 4;
        QualitySettings.anisotropicFiltering = AnisotropicFiltering.ForceEnable;
        QualitySettings.realtimeReflectionProbes = true;

        // Create custom dark midnight procedural Skybox Material
        Shader skyShader = Shader.Find("Skybox/Procedural");
        Material skyMat = AssetDatabase.LoadAssetAtPath<Material>("Assets/Materials/Mat_NightSky.mat");
        if (skyMat == null)
        {
            skyMat = new Material(skyShader);
            AssetDatabase.CreateAsset(skyMat, "Assets/Materials/Mat_NightSky.mat");
        }
        skyMat.SetFloat("_SunSize", 0.015f);
        skyMat.SetFloat("_AtmosphereThickness", 0.32f);
        skyMat.SetColor("_SkyTint", new Color(0.03f, 0.05f, 0.08f, 1f));
        skyMat.SetColor("_GroundColor", new Color(0.02f, 0.03f, 0.04f, 1f));
        skyMat.SetFloat("_Exposure", 0.28f);
        EditorUtility.SetDirty(skyMat);

        RenderSettings.skybox = skyMat;
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.032f, 0.048f, 0.072f);
        RenderSettings.ambientEquatorColor = new Color(0.022f, 0.034f, 0.050f);
        RenderSettings.ambientGroundColor = new Color(0.010f, 0.015f, 0.022f);
        RenderSettings.fog = true;
        RenderSettings.fogMode = FogMode.ExponentialSquared;
        RenderSettings.fogColor = new Color(0.035f, 0.055f, 0.075f);
        RenderSettings.fogDensity = 0.024f;

        Transform envRoot = new GameObject("01_VillageArchitecture").transform;
        Transform shrineRoot = new GameObject("02_ShrineAndSando").transform;
        Transform propsRoot = new GameObject("03_StreetClutterAndProps").transform;
        Transform foliageRoot = new GameObject("04_CedarForestAndBamboo").transform;
        Transform lightRoot = new GameObject("05_AtmosphericLighting").transform;

        // Load custom synthesized audio clips
        AudioClip clipRainWind = AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/Audio/Ambience_NightRainWind.wav");
        AudioClip clipHum = AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/Audio/Hum_FluorescentVending.wav");
        AudioClip clipClick = AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/Audio/SFX_FlashlightClick.wav");
        AudioClip clipBell = AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/Audio/SFX_ShrineSuzuBell.wav");
        AudioClip clipStinger = AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/Audio/SFX_HorrorStinger.wav");
        AudioClip[] wetSteps = new AudioClip[]
        {
            AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/Audio/Footstep_WetAsphalt_1.wav"),
            AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/Audio/Footstep_WetAsphalt_2.wav"),
            AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/Audio/Footstep_WetAsphalt_3.wav"),
            AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/Audio/Footstep_WetAsphalt_4.wav")
        };
        AudioClip[] stoneSteps = new AudioClip[]
        {
            AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/Audio/Footstep_Stone_1.wav"),
            AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/Audio/Footstep_Stone_2.wav")
        };

        // 1. Ground & Wet Asphalt Alley Road
        GameObject groundBase = GameObject.CreatePrimitive(PrimitiveType.Plane);
        groundBase.name = "VillageGroundBase";
        groundBase.transform.SetParent(envRoot, false);
        groundBase.transform.position = new Vector3(0f, -0.02f, 8f);
        groundBase.transform.localScale = new Vector3(12f, 1f, 12f);
        Material groundTiledMat = new Material(_materials["StonePaving"]);
        groundTiledMat.mainTextureScale = new Vector2(42f, 42f);
        AssetDatabase.DeleteAsset("Assets/Materials/Mat_GroundTiled.mat");
        AssetDatabase.CreateAsset(groundTiledMat, "Assets/Materials/Mat_GroundTiled.mat");
        groundBase.GetComponent<MeshRenderer>().sharedMaterial = groundTiledMat;

        SpawnModel("AlleyRoadAndGutters", "MainAlleyRoad", envRoot, Vector3.zero, Vector3.zero, Vector3.one);

        //Note on FBX orientation from Blender (axis_forward=-Z, axis_up=Y):
        // Blender +Y -> Unity -Z, Blender -Y (Front Facade) -> Unity +Z!
        // Let's orient West-side houses (X < 0) with rotY = 90 (so +Z faces +X toward street),
        // and East-side houses (X > 0) with rotY = -90 (so +Z faces -X toward street)!

        // 2. South Entrance: Rural Bus Stop (West side) & Corner Store + Vending Machine + Postbox (East side)
        GameObject busStop = SpawnModel("RuralBusStop", "BusStop_Yugiri", envRoot, new Vector3(-3.55f, 0.02f, -13.5f), new Vector3(0f, 90f, 0f), Vector3.one);
        AttachInteractable(
            busStop,
            "유우기리 마을 정류장 (夕霧村 停留所)",
            "『막차 23:45 (운휴)』 시간표 아래 붉은 매직으로 휘갈겨 쓴 경고문이 있다:\n「안개가 골목을 채우면 집 안의 불빛을 들여다보지 마라. 그건 사람이 아니다.」"
        );

        GameObject cornerStore = SpawnModel("CornerStore_Dagashiya", "CornerStore_YugiriShoten", envRoot, new Vector3(5.65f, 0f, -12.2f), new Vector3(0f, -90f, 0f), Vector3.one);
        AttachInteractable(
            cornerStore,
            "유우기리 상점 (たばこ・駄菓子 夕霧商店)",
            "굳게 닫힌 녹슨 철제 셔터 안쪽에서 오래된 라디오 잡음과 함께 누군가 중얼거리는 소리가 들려온다..."
        );

        GameObject vending = SpawnModel("RetroVendingMachine", "VendingMachine_Jihanki", propsRoot, new Vector3(2.35f, 0.02f, -8.6f), new Vector3(0f, -85f, 0f), Vector3.one);
        AttachInteractable(
            vending,
            "24시간 자동판매기 (自動販売機)",
            "차가운 푸른 형광등 불빛이 젖은 아스팔트 물웅덩이 위에 번진다. 동전 반환구 속에 붉게 물든 신사 부적 조각이 들어 있다."
        );
        if (vending != null && clipHum != null)
        {
            AudioSource humSrc = vending.AddComponent<AudioSource>();
            humSrc.clip = clipHum;
            humSrc.loop = true;
            humSrc.spatialBlend = 1.0f;
            humSrc.minDistance = 1.2f;
            humSrc.maxDistance = 11.0f;
            humSrc.volume = 0.55f;
            humSrc.Play();
        }

        GameObject postbox = SpawnModel("Prop_Postbox", "ShowaPostbox", propsRoot, new Vector3(2.35f, 0.02f, -15.2f), new Vector3(0f, -65f, 0f), Vector3.one);
        AttachInteractable(
            postbox,
            "구형 원통 우체통 (郵便ポスト)",
            "투입구 안쪽이 검은 진흙과 말라붙은 솔잎으로 가득 막혀 있다. 수십 년 전부터 수거되지 않은 듯하다."
        );

        // 3. Closely Packed Traditional 2-Story Machiya & Showa Houses Lining Both Sides of the Narrow Alley
        // West Side (X = -5.55f, facing East +X -> rotY = 90)
        SpawnModel("MachiyaHouse_A", "Machiya_West_01", envRoot, new Vector3(-5.65f, 0f, -5.8f), new Vector3(0f, 90f, 0f), Vector3.one);
        SpawnModel("MachiyaHouse_B", "Machiya_West_02", envRoot, new Vector3(-5.45f, 0f, 2.2f), new Vector3(0f, 88f, 0f), Vector3.one);
        SpawnModel("MachiyaHouse_A", "Machiya_West_03", envRoot, new Vector3(-5.60f, 0f, 10.4f), new Vector3(0f, 92f, 0f), Vector3.one);
        SpawnModel("MachiyaHouse_B", "Machiya_West_04", envRoot, new Vector3(-5.50f, 0f, 17.5f), new Vector3(0f, 90f, 0f), Vector3.one);

        // East Side (X = +5.55f, facing West -X -> rotY = -90)
        SpawnModel("MachiyaHouse_B", "Machiya_East_01", envRoot, new Vector3(5.50f, 0f, -3.8f), new Vector3(0f, -92f, 0f), Vector3.one);
        SpawnModel("MachiyaHouse_A", "Machiya_East_02", envRoot, new Vector3(5.65f, 0f, 4.4f), new Vector3(0f, -90f, 0f), Vector3.one);
        SpawnModel("MachiyaHouse_B", "Machiya_East_03", envRoot, new Vector3(5.45f, 0f, 12.6f), new Vector3(0f, -88f, 0f), Vector3.one);

        // South Alley Cul-de-Sac Blocking Building & Boundary Wall (Z = -24.5m) so the South horizon is completely enclosed
        SpawnModel("MachiyaHouse_A", "Machiya_SouthBlock", envRoot, new Vector3(0.4f, 0f, -24.5f), new Vector3(0f, 0f, 0f), Vector3.one);
        SpawnModel("ConcreteBlockWall_Segment", "Wall_SouthBlock_L", envRoot, new Vector3(-4.2f, 0f, -20.8f), new Vector3(0f, 25f, 0f), Vector3.one);
        SpawnModel("ConcreteBlockWall_Segment", "Wall_SouthBlock_R", envRoot, new Vector3(4.2f, 0f, -20.8f), new Vector3(0f, -25f, 0f), Vector3.one);

        // Boundary Concrete Block Walls (CB塀) & Charred Wood Fences (Itabei) connecting houses along the alley
        SpawnModel("ConcreteBlockWall_Segment", "CBWall_West_1", envRoot, new Vector3(-2.85f, 0f, -10.0f), new Vector3(0f, 90f, 0f), Vector3.one);
        SpawnModel("WoodenFence_Segment", "WoodFence_West_1", envRoot, new Vector3(-2.85f, 0f, -1.6f), new Vector3(0f, 0f, 0f), Vector3.one);
        SpawnModel("ConcreteBlockWall_Segment", "CBWall_West_2", envRoot, new Vector3(-2.85f, 0f, 6.4f), new Vector3(0f, 90f, 0f), Vector3.one);
        SpawnModel("WoodenFence_Segment", "WoodFence_West_2", envRoot, new Vector3(-2.85f, 0f, 14.2f), new Vector3(0f, 0f, 0f), Vector3.one);

        SpawnModel("ConcreteBlockWall_Segment", "CBWall_East_1", envRoot, new Vector3(2.85f, 0f, -7.8f), new Vector3(0f, 90f, 0f), Vector3.one);
        SpawnModel("WoodenFence_Segment", "WoodFence_East_1", envRoot, new Vector3(2.85f, 0f, 0.5f), new Vector3(0f, 0f, 0f), Vector3.one);
        SpawnModel("ConcreteBlockWall_Segment", "CBWall_East_2", envRoot, new Vector3(2.85f, 0f, 8.6f), new Vector3(0f, 90f, 0f), Vector3.one);
        SpawnModel("ConcreteBlockWall_Segment", "CBWall_East_3", envRoot, new Vector3(2.85f, 0f, 16.8f), new Vector3(0f, 90f, 0f), Vector3.one);

        // 4. Concrete Utility Poles (Denchu) & Overhead Catenary Electrical Wires
        float[] poleZ = new float[] { -14.5f, -4.5f, 5.5f, 15.5f };
        for (int i = 0; i < poleZ.Length; i++)
        {
            bool eastSide = (i % 2 == 0);
            float px = eastSide ? 2.45f : -2.45f;
            float ry = eastSide ? 0f : 180f;
            SpawnModel("UtilityPole_Denchu", $"UtilityPole_{i + 1}", propsRoot, new Vector3(px, 0f, poleZ[i]), new Vector3(0f, ry, 0f), Vector3.one);

            // Warm sodium / eerie mercury streetlamp under each pole's hood
            float lampX = eastSide ? (px - 1.22f) : (px + 1.22f);
            Color lampCol = (i == 2) ? new Color(0.68f, 0.92f, 1.0f) : new Color(1.0f, 0.72f, 0.38f);
            Light spot = CreateLight($"Streetlamp_Spot_{i + 1}", lightRoot, LightType.Spot, new Vector3(lampX, 4.95f, poleZ[i]), new Vector3(90f, 0f, 0f), lampCol, 3.4f, 14.0f, 106f, true);
            Light point = CreateLight($"Streetlamp_Halo_{i + 1}", lightRoot, LightType.Point, new Vector3(lampX, 4.80f, poleZ[i]), Vector3.zero, lampCol, 1.35f, 8.8f, 60f, false);
            CreateVolumetricLightCone($"Streetlamp_VolCone_{i + 1}", lightRoot, new Vector3(lampX, 2.45f, poleZ[i]), 0.18f, 2.85f, 4.95f, new Color(lampCol.r, lampCol.g, lampCol.b, 0.085f));

            if (i == 1 || i == 2)
            {
                YugiriLightFlicker fl = spot.gameObject.AddComponent<YugiriLightFlicker>();
                fl.style = (i == 2) ? YugiriLightFlicker.FlickerStyle.DamagedStreetlamp : YugiriLightFlicker.FlickerStyle.FluorescentHum;
                fl.baseIntensity = 3.4f;
                fl.amplitude = 0.65f;
            }
        }

        // Overhead sagging cable spans along both sides and crossing the alley
        for (int i = 0; i < 3; i++)
        {
            float midZ = -9.5f + i * 10.0f;
            SpawnModel("OverheadCables_Span", $"Cables_East_{i}", propsRoot, new Vector3(2.35f, 7.65f, midZ), Vector3.zero, Vector3.one);
            SpawnModel("OverheadCables_Span", $"Cables_West_{i}", propsRoot, new Vector3(-2.35f, 7.55f, midZ), Vector3.zero, Vector3.one);
            SpawnModel("OverheadCables_Span", $"Cables_Cross_{i}", propsRoot, new Vector3(0f, 7.35f, midZ + 2.5f), new Vector3(0f, 28f * (i % 2 == 0 ? 1 : -1), 0f), new Vector3(0.6f, 1f, 0.65f));
        }

        // 5. High-Density Alley Clutter: Outdoor AC Units, Bicycles, Curve Mirrors, Trash Bins, Potted Plants
        Vector3[] acPositions = new Vector3[]
        {
            new Vector3(-2.55f, 0.35f, -7.2f),
            new Vector3(-2.55f, 1.65f, -6.2f),
            new Vector3(-2.55f, 0.35f, 1.1f),
            new Vector3(-2.55f, 0.35f, 9.2f),
            new Vector3(2.55f, 0.35f, -10.2f),
            new Vector3(2.55f, 0.35f, -2.5f),
            new Vector3(2.55f, 1.55f, -2.5f),
            new Vector3(2.55f, 0.35f, 5.8f),
            new Vector3(2.55f, 0.35f, 13.5f)
        };
        for (int i = 0; i < acPositions.Length; i++)
        {
            float ry = acPositions[i].x < 0 ? 90f : -90f;
            SpawnModel("Prop_ACUnit", $"ACUnit_{i + 1}", propsRoot, acPositions[i], new Vector3(0f, ry, 0f), Vector3.one);
        }

        Vector3[] clutterPos = new Vector3[]
        {
            new Vector3(-2.25f, 0.02f, -8.4f),
            new Vector3(2.25f, 0.02f, -6.4f),
            new Vector3(-2.20f, 0.02f, -0.4f),
            new Vector3(2.22f, 0.02f, 2.8f),
            new Vector3(-2.25f, 0.02f, 7.8f),
            new Vector3(2.20f, 0.02f, 11.2f),
            new Vector3(-2.22f, 0.02f, 15.8f)
        };
        for (int i = 0; i < clutterPos.Length; i++)
        {
            SpawnModel("Prop_AlleyClutter", $"AlleyClutter_{i + 1}", propsRoot, clutterPos[i], new Vector3(0f, i * 52f, 0f), Vector3.one);
        }

        SpawnModel("Prop_Bicycle", "Bicycle_01", propsRoot, new Vector3(-2.30f, 0.02f, -11.4f), new Vector3(0f, 14f, 5f), Vector3.one);
        SpawnModel("Prop_Bicycle", "Bicycle_02", propsRoot, new Vector3(2.35f, 0.02f, -1.2f), new Vector3(0f, 168f, -4f), Vector3.one);
        SpawnModel("Prop_Bicycle", "Bicycle_03", propsRoot, new Vector3(-2.30f, 0.02f, 4.6f), new Vector3(0f, -12f, 4f), Vector3.one);
        SpawnModel("Prop_Bicycle", "Bicycle_04", propsRoot, new Vector3(2.32f, 0.02f, 14.8f), new Vector3(0f, 192f, -5f), Vector3.one);

        GameObject mirror1 = SpawnModel("Prop_CurveMirror", "CurveMirror_South", propsRoot, new Vector3(-2.38f, 0.02f, -3.2f), new Vector3(0f, 145f, 0f), Vector3.one);
        GameObject mirror2 = SpawnModel("Prop_CurveMirror", "CurveMirror_North", propsRoot, new Vector3(2.38f, 0.02f, 17.8f), new Vector3(0f, -155f, 0f), Vector3.one);
        AttachInteractable(
            mirror2,
            "출입금지 경고판 (立入禁止)",
            "『이곳부터 유우기리 신사 경내 — 일몰 후 참배 및 출입을 엄금함. 어길 시 실종에 대해 마을은 책임지지 않음.』"
        );

        // 6. North Stone Stairway (Sando), Twin Vermilion Torii Gates, Stone Lanterns (Ishidoro), Jizo Statues, & Main Yugiri Shrine!
        // Note: In Blender, ShrineStoneSteps_Sando goes in +Y (0 to +21.6m). With axis_forward=-Z, +Y in Blender is -Z in Unity unless rotated 180 deg!
        // Rotating 180 degrees around Y makes Blender +Y point straight toward Unity +Z (North)!
        SpawnModel("ShrineStoneSteps_Sando", "ShrineStoneSteps_Sando", shrineRoot, new Vector3(0f, 0f, 20.0f), new Vector3(0f, 180f, 0f), Vector3.one);

        // First Grand Torii Gate at the base of the stone steps (Z = 19.2m)
        GameObject torii1 = SpawnModel("ToriiGate_Grand", "ToriiGate_Lower", shrineRoot, new Vector3(0f, 0f, 19.2f), new Vector3(0f, 180f, 0f), Vector3.one);
        AttachInteractable(
            torii1,
            "유우기리 신사 이치노토리이 (一の鳥居)",
            "빛바랜 주홍빛 기둥에 걸린 금줄(시메나와)이 축축한 밤바람에 흔들린다. 현판에는 『夕霧神社(유우기리 신사)』라 새겨져 있다."
        );

        // Second Torii Gate at the top of the stone steps (Z = 29.0m, Y = 3.24m)
        SpawnModel("ToriiGate_Grand", "ToriiGate_Upper", shrineRoot, new Vector3(0f, 3.24f, 29.2f), new Vector3(0f, 180f, 0f), new Vector3(0.92f, 0.92f, 0.92f));

        // 8 Stone Lanterns (Ishidoro) & 6 Jizo Statues lining the stairs and shrine courtyard
        float[] lanternZ = new float[] { 18.2f, 22.0f, 26.0f, 31.2f };
        float[] lanternY = new float[] { 0.02f, 0.95f, 2.35f, 3.24f };
        for (int i = 0; i < lanternZ.Length; i++)
        {
            for (int side = -1; side <= 1; side += 2)
            {
                float lx = side * (i == 3 ? 2.85f : 2.35f);
                GameObject lan = SpawnModel("StoneLantern_Ishidoro", $"Ishidoro_{i}_{(side < 0 ? "L" : "R")}", shrineRoot, new Vector3(lx, lanternY[i], lanternZ[i]), Vector3.zero, Vector3.one);
                Light flame = CreateLight(
                    $"LanternFlame_{i}_{(side < 0 ? "L" : "R")}",
                    lightRoot,
                    LightType.Point,
                    new Vector3(lx, lanternY[i] + 1.54f, lanternZ[i]),
                    Vector3.zero,
                    new Color(1.0f, 0.56f, 0.20f),
                    2.15f,
                    7.5f,
                    60f,
                    false
                );
                YugiriLightFlicker fl = flame.gameObject.AddComponent<YugiriLightFlicker>();
                fl.style = YugiriLightFlicker.FlickerStyle.CandleFlame;
                fl.baseIntensity = 2.15f;
                fl.amplitude = 0.45f;
            }
        }

        for (int i = 0; i < 3; i++)
        {
            float jz = 20.5f + i * 3.2f;
            float jy = 0.45f + i * 1.10f;
            GameObject jizoL = SpawnModel("Prop_JizoStatue", $"Jizo_L_{i}", shrineRoot, new Vector3(-1.95f, jy, jz), new Vector3(0f, 105f, 0f), Vector3.one);
            GameObject jizoR = SpawnModel("Prop_JizoStatue", $"Jizo_R_{i}", shrineRoot, new Vector3(1.95f, jy, jz), new Vector3(0f, -105f, 0f), Vector3.one);
            if (i == 0)
            {
                AttachInteractable(
                    jizoL,
                    "붉은 턱받이 지장보살상 (地蔵菩薩)",
                    "이끼 낀 돌계단 옆 지장보살상들이 모두 신사 본전이 아닌 당신이 걸어온 골목 아래쪽을 응시하고 있다.",
                    null,
                    clipStinger,
                    false
                );
            }
        }

        // Main Yugiri Shrine Building (YugiriShrine_Hokora) at top of courtyard (Z = 36.2m, Y = 3.24m)
        GameObject mainShrine = SpawnModel("YugiriShrine_Hokora", "YugiriShrine_Hokora", shrineRoot, new Vector3(0f, 3.24f, 36.2f), new Vector3(0f, 180f, 0f), Vector3.one);
        AttachInteractable(
            mainShrine,
            "유우기리 신사 본전 새전함 (夕霧神社 賽銭箱)",
            "녹슨 방울 줄을 흔들자 무거운 방울 소리가 안개 속으로 울려 퍼진다.\n본전 문틈 너머에서 누군가의 차가운 시선이 느껴지고, 모든 석등의 불빛이 핏빛으로 일렁인다!",
            clipBell,
            clipStinger,
            true
        );

        GameObject emaWell = SpawnModel("Prop_EmaRackAndWell", "ShrineEmaAndWell", shrineRoot, new Vector3(-4.2f, 3.24f, 30.8f), new Vector3(0f, 150f, 0f), Vector3.one);
        AttachInteractable(
            emaWell,
            "소원패 걸이와 봉인된 우물 (絵馬掛け・古井戸)",
            "수십 개의 나무 에마(소원패)에 똑같은 문장이 검게 적혀 있다:\n『돌려보내 주세요 (帰してください)』"
        );

        // 7. Dense Japanese Cedar Forest (Sugi) enclosing the Shrine, Steps, and Alley Horizon
        Vector3[] treePositions = new Vector3[]
        {
            new Vector3(-5.2f, 0f, 19.5f), new Vector3(5.2f, 0f, 19.5f),
            new Vector3(-4.8f, 1.2f, 23.5f), new Vector3(4.8f, 1.2f, 23.5f),
            new Vector3(-5.4f, 2.4f, 27.5f), new Vector3(5.4f, 2.4f, 27.5f),
            new Vector3(-6.2f, 3.2f, 31.5f), new Vector3(6.2f, 3.2f, 31.5f),
            new Vector3(-6.5f, 3.2f, 35.5f), new Vector3(6.5f, 3.2f, 35.5f),
            new Vector3(-5.5f, 3.2f, 39.5f), new Vector3(5.5f, 3.2f, 39.5f),
            new Vector3(-2.5f, 3.2f, 41.0f), new Vector3(2.5f, 3.2f, 41.0f),
            new Vector3(0.0f, 3.2f, 41.8f),
            new Vector3(-8.5f, 0f, -18.0f), new Vector3(8.5f, 0f, -18.0f),
            new Vector3(-4.5f, 0f, -21.5f), new Vector3(4.8f, 0f, -21.5f),
            new Vector3(-8.8f, 0f, -9.0f), new Vector3(8.8f, 0f, -9.0f),
            new Vector3(-8.8f, 0f, 0.0f), new Vector3(8.8f, 0f, 0.0f),
            new Vector3(-8.8f, 0f, 9.0f), new Vector3(8.8f, 0f, 9.0f),
            new Vector3(-8.8f, 0f, 16.0f), new Vector3(8.8f, 0f, 16.0f)
        };
        for (int i = 0; i < treePositions.Length; i++)
        {
            float s = 0.88f + (i % 4) * 0.12f;
            SpawnModel("Tree_SugiCedar", $"SugiCedar_{i + 1}", foliageRoot, treePositions[i], new Vector3(0f, i * 47f, 0f), new Vector3(s, s, s));
        }

        // 7b. Lush 3D Wet Botanical Clusters (Woodland Ferns, Veined Hosta Broadleaves & Wild Grass) along curbs, walls & stone steps
        Vector3[] foliageClusterPos = new Vector3[]
        {
            new Vector3(-2.45f, 0.01f, -15.6f), new Vector3(2.45f, 0.01f, -14.0f),
            new Vector3(-2.42f, 0.01f, -11.0f), new Vector3(2.42f, 0.01f, -9.2f),
            new Vector3(-2.46f, 0.01f, -6.2f),  new Vector3(2.44f, 0.01f, -4.8f),
            new Vector3(-2.42f, 0.01f, -1.8f),  new Vector3(2.42f, 0.01f, 0.6f),
            new Vector3(-2.45f, 0.01f, 3.8f),   new Vector3(2.45f, 0.01f, 5.2f),
            new Vector3(-2.42f, 0.01f, 8.8f),   new Vector3(2.42f, 0.01f, 10.4f),
            new Vector3(-2.45f, 0.01f, 13.6f),  new Vector3(2.45f, 0.01f, 15.2f),
            new Vector3(-2.15f, 0.02f, 18.6f),  new Vector3(2.15f, 0.02f, 18.6f),
            new Vector3(-2.10f, 0.62f, 21.2f),  new Vector3(2.10f, 0.62f, 21.2f),
            new Vector3(-2.10f, 1.52f, 23.8f),  new Vector3(2.10f, 1.52f, 23.8f),
            new Vector3(-2.10f, 2.42f, 26.5f),  new Vector3(2.10f, 2.42f, 26.5f),
            new Vector3(-2.95f, 3.25f, 31.8f),  new Vector3(2.95f, 3.25f, 31.8f)
        };
        for (int i = 0; i < foliageClusterPos.Length; i++)
        {
            float fs = 0.85f + (i % 3) * 0.16f;
            SpawnModel("Prop_WetFoliageCluster", $"WetFoliageCluster_{i + 1}", foliageRoot, foliageClusterPos[i], new Vector3(0f, i * 67f, 0f), new Vector3(fs, fs, fs));
        }

        // 8. Atmospheric Fill & Accent Lights (Vending machine glow, Bus Stop fluorescent, Shoji window spills, Shrine inner glow, Moonlight)
        CreateLight("Moonlight_Directional", lightRoot, LightType.Directional, new Vector3(0f, 20f, 0f), new Vector3(48f, -32f, 0f), new Color(0.24f, 0.36f, 0.52f), 0.16f, 100f, 60f, true);

        // Vending machine cold cyan-white glow onto wet asphalt puddles
        CreateLight("VendingMachine_Glow", lightRoot, LightType.Point, new Vector3(2.15f, 1.15f, -8.3f), Vector3.zero, new Color(0.62f, 0.86f, 1.0f), 2.25f, 8.5f, 60f, true);

        // Bus stop flickering eerie fluorescent light
        Light busLight = CreateLight("BusStop_Fluorescent", lightRoot, LightType.Point, new Vector3(-3.1f, 2.25f, -13.5f), Vector3.zero, new Color(0.68f, 0.88f, 0.82f), 1.45f, 7.5f, 60f, false);
        YugiriLightFlicker busFl = busLight.gameObject.AddComponent<YugiriLightFlicker>();
        busFl.style = YugiriLightFlicker.FlickerStyle.FluorescentHum;
        busFl.baseIntensity = 1.45f;
        busFl.amplitude = 0.40f;

        // Warm amber & eerie Shoji window bounce lights along the alley
        CreateLight("WindowGlow_West1", lightRoot, LightType.Point, new Vector3(-2.3f, 3.8f, -5.8f), Vector3.zero, new Color(1.0f, 0.62f, 0.25f), 0.85f, 6.0f, 60f, false);
        CreateLight("WindowGlow_East1", lightRoot, LightType.Point, new Vector3(2.3f, 3.8f, 4.4f), Vector3.zero, new Color(1.0f, 0.62f, 0.25f), 0.85f, 6.0f, 60f, false);
        CreateLight("WindowGlow_Eerie", lightRoot, LightType.Point, new Vector3(-2.3f, 3.8f, 2.2f), Vector3.zero, new Color(0.45f, 0.88f, 0.72f), 0.80f, 5.5f, 60f, false);

        // Shrine Sanctuary warm mysterious glow
        CreateLight("ShrineSanctuary_Glow", lightRoot, LightType.Point, new Vector3(0f, 5.2f, 33.8f), Vector3.zero, new Color(1.0f, 0.48f, 0.18f), 2.2f, 10.5f, 60f, true);

        // 9. First-Person Player Rig (CharacterController + Camera + PostFX + Flashlight + Spatial Rain + Ambience)
        GameObject playerGo = new GameObject("Player_FirstPerson");
        playerGo.tag = "Player";
        playerGo.transform.position = new Vector3(-0.35f, 0.05f, -16.2f);
        playerGo.transform.eulerAngles = new Vector3(0f, 4f, 0f);

        CharacterController cc = playerGo.AddComponent<CharacterController>();
        cc.height = 1.78f;
        cc.radius = 0.34f;
        cc.center = new Vector3(0f, 0.89f, 0f);
        cc.stepOffset = 0.32f;
        cc.slopeLimit = 50f;

        GameObject camGo = new GameObject("Main Camera");
        camGo.tag = "MainCamera";
        camGo.transform.SetParent(playerGo.transform, false);
        camGo.transform.localPosition = new Vector3(0f, 1.66f, 0f);
        camGo.transform.localRotation = Quaternion.identity;

        Camera cam = camGo.AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.Skybox;
        cam.backgroundColor = new Color(0.02f, 0.03f, 0.05f, 1f);
        cam.nearClipPlane = 0.08f;
        cam.farClipPlane = 110f;
        cam.fieldOfView = 62f;
        cam.allowHDR = true;
        cam.allowMSAA = true;
        cam.depthTextureMode = DepthTextureMode.Depth;
        camGo.AddComponent<AudioListener>();

        YugiriPostProcessing postFx = camGo.AddComponent<YugiriPostProcessing>();
        postFx.postShader = Shader.Find("Hidden/YugiriHorrorPostFX");
        postFx.fogDensity = 0.026f;
        postFx.bloomIntensity = 0.62f;
        postFx.bloomThreshold = 0.68f;
        postFx.vignetteIntensity = 0.42f;
        postFx.grainIntensity = 0.020f;
        postFx.aoIntensity = 0.65f;
        postFx.exposure = 1.08f;

        // Tactical Handheld Flashlight (Spot + soft wide Spill)
        GameObject flashGo = new GameObject("PlayerFlashlight");
        flashGo.transform.SetParent(camGo.transform, false);
        flashGo.transform.localPosition = new Vector3(0.18f, -0.14f, 0.12f);
        Light flashSpot = flashGo.AddComponent<Light>();
        flashSpot.type = LightType.Spot;
        flashSpot.color = new Color(0.96f, 0.95f, 0.88f);
        flashSpot.intensity = 2.65f;
        flashSpot.range = 24f;
        flashSpot.spotAngle = 48f;
        flashSpot.innerSpotAngle = 22f;
        flashSpot.shadows = LightShadows.Soft;

        GameObject spillGo = new GameObject("FlashlightSpill");
        spillGo.transform.SetParent(flashGo.transform, false);
        Light flashSpill = spillGo.AddComponent<Light>();
        flashSpill.type = LightType.Spot;
        flashSpill.color = new Color(0.82f, 0.88f, 0.95f);
        flashSpill.intensity = 0.75f;
        flashSpill.range = 10f;
        flashSpill.spotAngle = 88f;
        flashSpill.shadows = LightShadows.None;

        // Audio Sources on Player
        AudioSource ambSrc = playerGo.AddComponent<AudioSource>();
        ambSrc.clip = clipRainWind;
        ambSrc.loop = true;
        ambSrc.spatialBlend = 0f;
        ambSrc.volume = 0.48f;
        ambSrc.playOnAwake = true;

        GameObject stepGo = new GameObject("FootstepAudio");
        stepGo.transform.SetParent(playerGo.transform, false);
        AudioSource stepSrc = stepGo.AddComponent<AudioSource>();
        stepSrc.spatialBlend = 0f;
        stepSrc.playOnAwake = false;

        GameObject sfxGo = new GameObject("InteractionSFXAudio");
        sfxGo.transform.SetParent(playerGo.transform, false);
        AudioSource sfxSrc = sfxGo.AddComponent<AudioSource>();
        sfxSrc.spatialBlend = 0f;
        sfxSrc.playOnAwake = false;

        YugiriFirstPersonController fpc = playerGo.AddComponent<YugiriFirstPersonController>();
        fpc.playerCamera = cam;
        fpc.flashlightSpot = flashSpot;
        fpc.flashlightSpill = flashSpill;
        fpc.flashlightClickClip = clipClick;
        fpc.footstepSource = stepSrc;
        fpc.sfxSource = sfxSrc;
        fpc.wetAsphaltSteps = wetSteps;
        fpc.stoneSteps = stoneSteps;

        // 10. Render 4 Local HDR Reflection Cubemaps along the Wet Alley & Shrine Courtyard BEFORE spawning rain particles
        BakeAlleyReflectionCubemap(cam, lightRoot);

        // 11. Multi-Zone 3D Rain Streaks & Pre-Simulated Rain Particles
        BuildRainParticles(playerGo.transform, lightRoot);

        string scenePath = "Assets/Scenes/YugiriVillage.unity";
        EditorSceneManager.SaveScene(scene, scenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(scenePath, true) };
    }

    private static void CreateVolumetricLightCone(string name, Transform parent, Vector3 pos, float topRadius, float bottomRadius, float height, Color color)
    {
        GameObject go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.transform.position = pos;

        MeshFilter mf = go.AddComponent<MeshFilter>();
        MeshRenderer mr = go.AddComponent<MeshRenderer>();
        mr.shadowCastingMode = ShadowCastingMode.Off;
        mr.receiveShadows = false;

        int segs = 24;
        Mesh m = new Mesh { name = name + "_Mesh" };
        Vector3[] verts = new Vector3[(segs + 1) * 2];
        Vector3[] norms = new Vector3[(segs + 1) * 2];
        Vector2[] uvs = new Vector2[(segs + 1) * 2];
        int[] tris = new int[segs * 6];

        float halfH = height * 0.5f;
        for (int i = 0; i <= segs; i++)
        {
            float t = (float)i / segs;
            float ang = t * Mathf.PI * 2f;
            float cx = Mathf.Cos(ang);
            float cz = Mathf.Sin(ang);

            verts[i] = new Vector3(cx * bottomRadius, -halfH, cz * bottomRadius);
            verts[i + segs + 1] = new Vector3(cx * topRadius, halfH, cz * topRadius);

            Vector3 n = new Vector3(cx, (bottomRadius - topRadius) / height, cz).normalized;
            norms[i] = n;
            norms[i + segs + 1] = n;

            uvs[i] = new Vector2(t, 0f);
            uvs[i + segs + 1] = new Vector2(t, 1f);
        }

        int ti = 0;
        for (int i = 0; i < segs; i++)
        {
            int b0 = i;
            int b1 = i + 1;
            int t0 = i + segs + 1;
            int t1 = i + segs + 2;

            tris[ti++] = b0;
            tris[ti++] = t0;
            tris[ti++] = b1;

            tris[ti++] = b1;
            tris[ti++] = t0;
            tris[ti++] = t1;
        }

        m.vertices = verts;
        m.normals = norms;
        m.uv = uvs;
        m.triangles = tris;
        mf.sharedMesh = m;

        Shader coneShader = Shader.Find("Custom/YugiriVolumetricCone");
        if (coneShader != null)
        {
            Material mat = new Material(coneShader);
            mat.SetColor("_Color", color);
            mr.sharedMaterial = mat;
        }
    }

    private static void BuildRainParticles(Transform playerTransform, Transform envRoot)
    {
        // Generate soft rain streak texture so particles never render as hard rectangles
        string rainTexPath = "Assets/Textures/RainStreakSoft.png";
        if (!File.Exists(rainTexPath))
        {
            int w = 32, h = 128;
            Texture2D rTex = new Texture2D(w, h, TextureFormat.RGBA32, false);
            for (int y = 0; y < h; y++)
            {
                float vy = (float)y / (h - 1);
                float yFade = Mathf.Sin(vy * Mathf.PI);
                for (int x = 0; x < w; x++)
                {
                    float vx = Mathf.Abs(((float)x / (w - 1)) * 2f - 1f);
                    float xFade = Mathf.Clamp01(1f - vx * vx);
                    float a = xFade * xFade * yFade;
                    rTex.SetPixel(x, y, new Color(0.82f, 0.90f, 1.0f, a));
                }
            }
            rTex.Apply();
            File.WriteAllBytes(rainTexPath, rTex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(rTex);
            AssetDatabase.ImportAsset(rainTexPath);
            TextureImporter ti = AssetImporter.GetAtPath(rainTexPath) as TextureImporter;
            if (ti != null)
            {
                ti.alphaIsTransparency = true;
                ti.wrapMode = TextureWrapMode.Clamp;
                ti.SaveAndReimport();
            }
        }
        Texture2D rainStreakTex = AssetDatabase.LoadAssetAtPath<Texture2D>(rainTexPath);

        string matPath = "Assets/Materials/Mat_RainStreak.mat";
        AssetDatabase.DeleteAsset(matPath);
        Shader partShader = Shader.Find("Legacy Shaders/Particles/Additive");
        if (partShader == null) partShader = Shader.Find("Particles/Standard Unlit");
        Material rainMat = new Material(partShader);
        rainMat.mainTexture = rainStreakTex;
        rainMat.SetColor("_TintColor", new Color(0.58f, 0.72f, 0.88f, 0.28f));
        rainMat.SetColor("_Color", new Color(0.58f, 0.72f, 0.88f, 0.28f));
        AssetDatabase.CreateAsset(rainMat, matPath);

        // Create 3 World-Space Rain Emitters covering South Alley, Mid Alley, and Shrine Steps/Courtyard + 1 on Player
        Vector3[] zones = new Vector3[]
        {
            new Vector3(0f, 9.5f, -13.0f),
            new Vector3(0f, 9.5f, 3.0f),
            new Vector3(0f, 12.5f, 24.0f)
        };

        for (int i = 0; i < zones.Length; i++)
        {
            GameObject rainGo = new GameObject($"WorldRainEmitter_{i + 1}");
            rainGo.transform.SetParent(envRoot, false);
            rainGo.transform.position = zones[i];
            rainGo.transform.eulerAngles = new Vector3(86f, 12f, 0f);

            ParticleSystem ps = rainGo.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.loop = true;
            main.prewarm = true;
            main.startLifetime = 0.68f;
            main.startSpeed = 19.5f;
            main.startSize = 0.032f;
            main.startColor = new Color(0.72f, 0.84f, 0.96f, 0.34f);
            main.maxParticles = 1600;
            main.simulationSpace = ParticleSystemSimulationSpace.World;

            var emission = ps.emission;
            emission.rateOverTime = 850f;

            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(16f, 18f, 1f);

            ParticleSystemRenderer psr = rainGo.GetComponent<ParticleSystemRenderer>();
            psr.renderMode = ParticleSystemRenderMode.Stretch;
            psr.lengthScale = 9.5f;
            psr.velocityScale = 0.09f;
            psr.sharedMaterial = rainMat;
            psr.shadowCastingMode = ShadowCastingMode.Off;

            // Advance simulation in Edit Mode so static renders & scene view immediately show falling rain!
            ps.Simulate(2.5f + i * 0.7f, true, true);
            ps.Play();
        }
    }

    private static void BakeAlleyReflectionCubemap(Camera mainCam, Transform lightRoot)
    {
        Vector3[] probePositions = new Vector3[]
        {
            new Vector3(0f, 1.35f, -12.0f),
            new Vector3(0f, 1.35f, -1.5f),
            new Vector3(0f, 1.65f, 16.5f),
            new Vector3(0f, 4.65f, 31.5f)
        };

        GameObject tempCamGo = new GameObject("TempCubemapCam");
        Camera cCam = tempCamGo.AddComponent<Camera>();
        cCam.clearFlags = CameraClearFlags.Skybox;
        cCam.backgroundColor = new Color(0.02f, 0.03f, 0.05f, 1f);
        cCam.nearClipPlane = 0.1f;
        cCam.farClipPlane = 85f;
        cCam.allowHDR = true;

        Cubemap defaultCube = null;
        for (int i = 0; i < probePositions.Length; i++)
        {
            tempCamGo.transform.position = probePositions[i];
            Cubemap cube = new Cubemap(256, TextureFormat.RGBAHalf, true);
            cCam.RenderToCubemap(cube);

            string cubePath = $"Assets/Textures/AlleyReflectionCubemap_{i}.asset";
            AssetDatabase.DeleteAsset(cubePath);
            AssetDatabase.CreateAsset(cube, cubePath);
            if (i == 1) defaultCube = cube;

            GameObject rpGo = new GameObject($"ReflectionProbe_{i + 1}");
            rpGo.transform.SetParent(lightRoot, false);
            rpGo.transform.position = probePositions[i];
            ReflectionProbe rp = rpGo.AddComponent<ReflectionProbe>();
            rp.mode = ReflectionProbeMode.Custom;
            rp.customBakedTexture = cube;
            rp.intensity = 1.65f;
            rp.size = new Vector3(16f, 14f, 18f);
            rp.boxProjection = true;
        }

        UnityEngine.Object.DestroyImmediate(tempCamGo);

        if (defaultCube != null)
        {
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
            RenderSettings.customReflectionTexture = defaultCube;
            RenderSettings.reflectionIntensity = 1.25f;
        }
    }
}
