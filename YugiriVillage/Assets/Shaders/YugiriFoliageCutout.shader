Shader "Custom/YugiriFoliageCutout"
{
    Properties
    {
        _Color ("Color", Color) = (1,1,1,1)
        _MainTex ("Albedo & Alpha (RGBA)", 2D) = "white" {}
        _Cutoff ("Alpha Cutoff", Range(0.05, 0.9)) = 0.35
        [Normal] _BumpMap ("Normal Map", 2D) = "bump" {}
        _BumpScale ("Normal Scale", Float) = 1.35
        _MetallicGlossMap ("Metallic (R) AO (G) Height (B) Smoothness (A)", 2D) = "white" {}
        _Glossiness ("Base Smoothness", Range(0,1)) = 0.82
        _Wetness ("Rain Wetness", Range(0,1)) = 0.88
        _WindStrength ("Breeze Sway Strength", Range(0, 0.1)) = 0.018
    }
    SubShader
    {
        Tags { "Queue"="AlphaTest" "IgnoreProjector"="True" "RenderType"="TransparentCutout" }
        LOD 300
        Cull Off

        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows alphatest:_Cutoff addshadow vertex:vert
        #pragma target 3.0

        sampler2D _MainTex;
        sampler2D _BumpMap;
        sampler2D _MetallicGlossMap;

        fixed4 _Color;
        half _BumpScale;
        half _Glossiness;
        half _Wetness;
        half _WindStrength;

        struct Input
        {
            float2 uv_MainTex;
            float3 worldPos;
            float3 worldNormal;
            INTERNAL_DATA
            fixed facing : VFACE;
        };

        float hash21_foliage(float2 p)
        {
            p = frac(p * float2(123.34, 456.21));
            p += dot(p, p + 45.32);
            return frac(p.x * p.y);
        }

        void vert(inout appdata_full v)
        {
            // Subtle rain-wind sway weighted by leaf tip distance (fract of UV.y inside each 0.5 quadrant)
            float3 wPos = mul(unity_ObjectToWorld, v.vertex).xyz;
            float tipWeight = frac(v.texcoord.y * 2.0);
            float phase = wPos.x * 2.3 + wPos.z * 1.9 + _Time.y * 2.6;
            float flutter = sin(phase) * 0.65 + cos(phase * 2.3 + wPos.y * 4.0) * 0.35;
            v.vertex.xyz += float3(flutter, -abs(flutter) * 0.35, flutter * 0.5) * (_WindStrength * tipWeight * tipWeight);
        }

        void surf (Input IN, inout SurfaceOutputStandard o)
        {
            fixed4 c = tex2D(_MainTex, IN.uv_MainTex) * _Color;

            // World-space botanical chlorophyll variation so adjacent plants & fronds have organic hue diversity
            float2 macroGrid = floor(IN.worldPos.xz * 1.7);
            float plantVar = hash21_foliage(macroGrid + floor(IN.worldPos.y * 2.0));
            float3 tintShift = lerp(float3(0.88, 0.96, 0.85), float3(1.14, 1.05, 0.92), plantVar);
            c.rgb *= tintShift;

            // Rain-soaked darkening on waxy cuticle
            c.rgb *= lerp(1.0, 0.78, _Wetness);

            float3 n = UnpackScaleNormal(tex2D(_BumpMap, IN.uv_MainTex), _BumpScale);
            if (IN.facing < 0)
            {
                n.z = -n.z;
            }

            // Microscopic raindrop bead normal glints on upper leaf surface
            float2 dropCell = floor(IN.uv_MainTex * 72.0);
            float2 dropLocal = frac(IN.uv_MainTex * 72.0) - 0.5;
            float dropSeed = hash21_foliage(dropCell);
            if (dropSeed > 0.68)
            {
                float r2 = dot(dropLocal, dropLocal);
                if (r2 < 0.14)
                {
                    n.xy += dropLocal * 2.4 * _Wetness;
                }
            }

            fixed4 mg = tex2D(_MetallicGlossMap, IN.uv_MainTex);
            float smooth = saturate(lerp(mg.a * _Glossiness, 0.92, _Wetness * 0.65));

            o.Albedo = c.rgb;
            o.Alpha = c.a;
            o.Normal = normalize(n);
            o.Metallic = 0.02;
            o.Smoothness = smooth;
            o.Occlusion = lerp(1.0, mg.g, 0.75);
            // Subtle dark-green subsurface ambient sheen so leaves never look pitch-black in deep shadow
            o.Emission = c.rgb * 0.06;
        }
        ENDCG
    }
    FallBack "Transparent/Cutout/VertexLit"
}
