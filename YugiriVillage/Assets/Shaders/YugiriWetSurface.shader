Shader "Custom/YugiriWetSurface"
{
    Properties
    {
        _Color ("Color", Color) = (1,1,1,1)
        _MainTex ("Albedo (RGB)", 2D) = "white" {}
        _BumpMap ("Normal Map", 2D) = "bump" {}
        _BumpScale ("Normal Scale", Float) = 1.0
        _MetallicGlossMap ("Metallic (R) AO (G) Height (B) Smoothness (A)", 2D) = "white" {}
        _GlossMapScale ("Smoothness Scale", Range(0, 1.5)) = 1.0
        _OcclusionMap ("Occlusion", 2D) = "white" {}
        _OcclusionStrength ("Occlusion Strength", Range(0, 1)) = 0.85
        _EmissionMap ("Emission", 2D) = "black" {}
        [HDR] _EmissionColor ("Emission Color", Color) = (0,0,0,1)
        _WetLevel ("Rain Wetness Level", Range(0, 1)) = 0.92
        _PuddleAmount ("Puddle Coverage", Range(0, 1)) = 0.65
        _RippleStrength ("Raindrop Ripple Strength", Range(0, 1)) = 0.32
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 300

        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows vertex:vert
        #pragma target 3.0

        sampler2D _MainTex;
        sampler2D _BumpMap;
        sampler2D _MetallicGlossMap;
        sampler2D _OcclusionMap;
        sampler2D _EmissionMap;

        fixed4 _Color;
        half _BumpScale;
        half _GlossMapScale;
        half _OcclusionStrength;
        half4 _EmissionColor;
        half _WetLevel;
        half _PuddleAmount;
        half _RippleStrength;

        struct Input
        {
            float2 uv_MainTex;
            float3 worldPos;
            float3 worldNormal;
            INTERNAL_DATA
        };

        void vert(inout appdata_full v, out Input o)
        {
            UNITY_INITIALIZE_OUTPUT(Input, o);
        }

        float2 hash22(float2 p)
        {
            float3 p3 = frac(float3(p.xyx) * float3(0.1031, 0.1030, 0.0973));
            p3 += dot(p3, p3.yzx + 33.33);
            return frac((p3.xx + p3.yz) * p3.zy);
        }

        float valueNoise(float2 p)
        {
            float2 i = floor(p);
            float2 f = frac(p);
            f = f * f * (3.0 - 2.0 * f);
            float a = frac(sin(dot(i, float2(127.1, 311.7))) * 43758.5453);
            float b = frac(sin(dot(i + float2(1.0, 0.0), float2(127.1, 311.7))) * 43758.5453);
            float c = frac(sin(dot(i + float2(0.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
            float d = frac(sin(dot(i + float2(1.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
            return lerp(lerp(a, b, f.x), lerp(c, d, f.x), f.y);
        }

        float fbmPuddle(float2 p)
        {
            float v = 0.0;
            v += 0.50 * valueNoise(p * 0.42);
            v += 0.30 * valueNoise(p * 0.95 + 11.3);
            v += 0.20 * valueNoise(p * 2.15 + 27.7);
            return v;
        }

        // Compute concentric expanding raindrop ripples in world XZ space
        float2 computeRainRipples(float2 wp, float timeVal)
        {
            float2 totalGrad = float2(0.0, 0.0);
            for (int layer = 0; layer < 3; layer++)
            {
                float scale = 2.4 + layer * 1.15;
                float2 uv = wp * scale + float2(layer * 17.3, layer * 31.7);
                float2 cell = floor(uv);
                float2 local = frac(uv) - 0.5;

                float2 rnd = hash22(cell);
                float2 dropCenter = (rnd - 0.5) * 0.45;
                float phase = frac(timeVal * 0.85 + rnd.x * 3.17 + rnd.y * 5.71);
                float2 delta = local - dropCenter;
                float dist = length(delta) + 1e-4;

                float ringRadius = phase * 0.44;
                float ringDiff = dist - ringRadius;
                float env = exp(-ringDiff * ringDiff * 195.0) * (1.0 - phase) * smoothstep(0.0, 0.08, phase);
                float wave = cos(ringDiff * 56.0) * env;
                totalGrad += (delta / dist) * wave;
            }
            return totalGrad;
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            fixed4 c = tex2D(_MainTex, IN.uv_MainTex) * _Color;
            float3 nrm = UnpackScaleNormal(tex2D(_BumpMap, IN.uv_MainTex), _BumpScale);
            fixed4 mg = tex2D(_MetallicGlossMap, IN.uv_MainTex);
            half occ = lerp(1.0, tex2D(_OcclusionMap, IN.uv_MainTex).r, _OcclusionStrength);
            half3 em = tex2D(_EmissionMap, IN.uv_MainTex).rgb * _EmissionColor.rgb;

            float3 geomN = WorldNormalVector(IN, float3(0, 0, 1));
            float upFactor = saturate((geomN.y - 0.65) * 3.2);
            float sideFactor = saturate(1.0 - abs(geomN.y) * 1.5);

            // 1. World-space macro weathering & grime variation (eliminates repetitive tiling across steps & walls)
            float macroVar = fbmPuddle(IN.worldPos.xz * 0.85 + float2(IN.worldPos.y * 1.3, -IN.worldPos.y * 0.7));
            float microSpeck = valueNoise(IN.worldPos.xz * 18.0 + IN.worldPos.y * 14.0);
            float isEmissive = saturate(dot(em, float3(0.33, 0.33, 0.33)) * 2.0);
            c.rgb *= lerp(0.86 + 0.26 * macroVar + 0.05 * (microSpeck - 0.5), 1.0, isEmissive);

            // 2. Detect velvety porous surfaces (bryophyte moss, lichen, woven cotton cloth bib) via low base smoothness (mg.a)
            float isVelvety = saturate((0.25 - mg.a) * 6.5) * (1.0 - mg.r);

            // 3. Height-aware puddle submergence (mg.b = surface micro-height)
            // Water fills low crevices and road depressions first, while aggregate tips and stone ridges poke out!
            float pNoise = fbmPuddle(IN.worldPos.xz);
            float roadCenterBias = saturate(1.0 - abs(IN.worldPos.x) * 0.38) * 0.14;
            float puddleBasin = smoothstep(0.54 - _PuddleAmount * 0.24, 0.74 - _PuddleAmount * 0.20, pNoise + roadCenterBias) * upFactor * _WetLevel;
            float surfaceHeight = mg.b;
            float waterHeight = puddleBasin * 0.78;
            float submerged = saturate((waterHeight - surfaceHeight * 0.58) * 5.2) * upFactor * (1.0 - isVelvety * 0.65);

            // 4. Concentric raindrop ripples strictly inside standing submerged water puddles
            float t = _Time.y + 4.25;
            float2 rippleGrad = computeRainRipples(IN.worldPos.xz, t) * _RippleStrength * (submerged * submerged) * upFactor;
            float3 puddleNrm = normalize(float3(rippleGrad.x, rippleGrad.y, 1.0));

            // 5. Vertical rainwater runoff streaks (雨筋) & ground splashback capillary soaking (雨跳ね)
            float wallSplash = saturate(1.0 - frac(IN.worldPos.y * 0.35) * 2.2) * saturate(1.5 - IN.worldPos.y * 0.85) * sideFactor * _WetLevel;
            float streakCoord = IN.worldPos.x * 6.5 + IN.worldPos.z * 6.5 + sin(IN.worldPos.y * 2.5) * 0.25;
            float streakNoise = valueNoise(float2(streakCoord, IN.worldPos.y * 0.45 + t * 0.28));
            float wallRivulet = smoothstep(0.56, 0.88, streakNoise) * sideFactor * _WetLevel * 0.48;
            float wetWall = saturate(wallSplash * 0.65 + wallRivulet);

            // 6. Physical porosity darkening when wet (porous wood, mortar, moss, and stone darken as water replaces air in pores)
            float porosity = saturate(1.0 - mg.r * 0.85);
            float wetAmount = saturate(submerged * 0.85 + puddleBasin * 0.35 + wetWall * 0.42 + upFactor * _WetLevel * 0.22);
            float darken = lerp(1.0, lerp(0.76, 0.54, porosity), wetAmount);
            c.rgb *= lerp(darken, 1.0, isEmissive);

            // Flatten normal to mirror water + ripples where submerged; slightly sharpen micro-facets on wet exposed stone!
            nrm.z = max(0.25, nrm.z);
            float3 wetExposedNrm = normalize(float3(nrm.xy * (1.0 + 0.15 * _WetLevel * (1.0 - isVelvety)), max(0.25, nrm.z)));
            nrm = normalize(lerp(wetExposedNrm, puddleNrm, submerged * 0.94));
            nrm.z = max(0.25, nrm.z);
            nrm = normalize(nrm);

            // 7. Material-Specific Wetness Smoothness:
            // - Velvety moss & cloth stay matte/velvety (0.14..0.24) because micro-hairs scatter light
            // - Exposed wet granite/asphalt aggregate gleams (0.72..0.88)
            // - Submerged standing water puddles become mirror-reflective (0.98)
            // - Vertical walls show contrasting wet runoff rivulets (+0.22 smoothness along rivulets)
            half baseSmooth = saturate(mg.a * _GlossMapScale);
            half horizExposedSmooth = lerp(max(baseSmooth, baseSmooth + 0.20 * _WetLevel), 0.16, isVelvety);
            half horizWetSmooth = lerp(horizExposedSmooth, 0.98, submerged);
            half vertWetSmooth = lerp(saturate(baseSmooth + wetWall * 0.22 + (macroVar - 0.5) * 0.06), 0.16, isVelvety);
            half targetSmooth = lerp(vertWetSmooth, horizWetSmooth, upFactor);

            o.Albedo = clamp(c.rgb, 0.0, 1.0);
            o.Normal = nrm;
            o.Metallic = saturate(lerp(mg.r, max(mg.r, lerp(0.06, 0.45, submerged)), upFactor * _WetLevel * (1.0 - isEmissive) * (1.0 - isVelvety)));
            o.Smoothness = clamp(lerp(baseSmooth, targetSmooth, _WetLevel * (1.0 - isEmissive * 0.85)), 0.04, 0.97);
            o.Occlusion = saturate(occ);
            o.Emission = clamp(em, 0.0, 8.0);
            o.Alpha = saturate(c.a);
        }
        ENDCG
    }
    FallBack "Standard"
}
