Shader "Hidden/YugiriHorrorPostFX"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
        _BloomTex ("Bloom", 2D) = "black" {}
        _FogColorNear ("Fog Color Near", Color) = (0.055, 0.082, 0.115, 1)
        _FogColorFar ("Fog Color Far", Color) = (0.020, 0.032, 0.052, 1)
        _FogDensity ("Fog Density", Float) = 0.024
        _BloomIntensity ("Bloom Intensity", Float) = 0.68
        _BloomThreshold ("Bloom Threshold", Float) = 0.58
        _VignetteIntensity ("Vignette Intensity", Float) = 0.42
        _GrainIntensity ("Grain Intensity", Float) = 0.016
        _AOIntensity ("AO Intensity", Float) = 0.65
        _Exposure ("Exposure", Float) = 1.16
        _ReflectionIntensity ("SSR Reflection Intensity", Float) = 0.88
        _RainIntensity ("Rain Intensity", Float) = 0.92
    }

    CGINCLUDE
    #include "UnityCG.cginc"

    sampler2D _MainTex;
    float4 _MainTex_TexelSize;
    sampler2D _BloomTex;
    sampler2D _CameraDepthTexture;
    sampler2D _CameraDepthNormalsTexture;

    float4 _FogColorNear;
    float4 _FogColorFar;
    float _FogDensity;
    float _BloomIntensity;
    float _BloomThreshold;
    float _VignetteIntensity;
    float _GrainIntensity;
    float _AOIntensity;
    float _Exposure;
    float _ReflectionIntensity;
    float _RainIntensity;
    float4 _BlurDir;

    float3 _CamPos;
    float3 _CamForward;
    float3 _CamRight;
    float3 _CamUp;
    float4 _CamFrustumParams; // x: tanHalfFov, y: aspect, z: near, w: far

    float hash12(float2 p)
    {
        float3 p3 = frac(float3(p.xyx) * 0.1031);
        p3 += dot(p3, p3.yzx + 33.33);
        return frac((p3.x + p3.y) * p3.z);
    }

    float2 hash22(float2 p)
    {
        float3 p3 = frac(float3(p.xyx) * float3(0.1031, 0.1030, 0.0973));
        p3 += dot(p3, p3.yzx + 33.33);
        return frac((p3.xx + p3.yz) * p3.zy);
    }

    float vnoise(float2 p)
    {
        float2 i = floor(p);
        float2 f = frac(p);
        f = f * f * (3.0 - 2.0 * f);
        float a = hash12(i);
        float b = hash12(i + float2(1.0, 0.0));
        float c = hash12(i + float2(0.0, 1.0));
        float d = hash12(i + float2(1.0, 1.0));
        return lerp(lerp(a, b, f.x), lerp(c, d, f.x), f.y);
    }

    float puddleFBM(float2 wp)
    {
        float v = 0.0;
        v += 0.55 * vnoise(wp * 0.42);
        v += 0.30 * vnoise(wp * 0.95 + 11.3);
        v += 0.15 * vnoise(wp * 2.10 + 27.7);
        return v;
    }

    // Concentric expanding raindrop ripples in world XZ space + splash crown
    float3 computeRipplesAndSplashes(float2 wp, float t)
    {
        float2 grad = float2(0.0, 0.0);
        float splash = 0.0;
        for (int layer = 0; layer < 3; layer++)
        {
            float scale = 2.6 + layer * 1.25;
            float2 uv = wp * scale + float2(layer * 17.3, layer * 31.7);
            float2 cell = floor(uv);
            float2 local = frac(uv) - 0.5;
            float2 rnd = hash22(cell);
            float2 center = (rnd - 0.5) * 0.44;
            float phase = frac(t * 0.85 + rnd.x * 3.17 + rnd.y * 5.71);
            float2 delta = local - center;
            float dist = length(delta) + 1e-4;

            float ringR = phase * 0.44;
            float diff = dist - ringR;
            float env = exp(-diff * diff * 190.0) * (1.0 - phase) * smoothstep(0.0, 0.07, phase);
            grad += (delta / dist) * (cos(diff * 62.0) * env);

            // Initial impact splash crown at phase 0.0..0.14
            float crownEnv = saturate(1.0 - phase * 7.5) * exp(-dist * dist * 420.0);
            splash += crownEnv;
        }
        return float3(grad, saturate(splash));
    }

    // Project a 3D world position P onto screen UV [0, 1]^2
    bool projectWorldToScreen(float3 P, out float2 outUV)
    {
        float3 toP = P - _CamPos;
        float pz = dot(toP, _CamForward);
        if (pz <= 0.15)
        {
            outUV = float2(-1.0, -1.0);
            return false;
        }
        float tanHalfFov = max(0.1, _CamFrustumParams.x);
        float aspect = max(0.1, _CamFrustumParams.y);
        float px = dot(toP, _CamRight) / (pz * aspect * tanHalfFov);
        float py = dot(toP, _CamUp) / (pz * tanHalfFov);
        outUV = float2(px, py) * 0.5 + 0.5;
        return (outUV.x > 0.01 && outUV.x < 0.99 && outUV.y > 0.01 && outUV.y < 0.99);
    }

    // High-speed motion-blurred rain streak sheet in screen/world space
    float evalRainStreakLayer(float2 uv, float scaleX, float scaleY, float speed, float windTilt, float seedOffset, float t)
    {
        float2 p = uv;
        p.x += (p.y - 0.5) * windTilt;
        float2 gridUV = float2(p.x * scaleX, p.y * scaleY + t * speed);
        float colId = floor(gridUV.x);
        float colRand = hash12(float2(colId, seedOffset));
        gridUV.y += colRand * 19.7;

        float2 cell = floor(gridUV);
        float2 f = frac(gridUV);
        float2 r = hash22(cell + seedOffset);
        if (r.x < 0.62) return 0.0; // Sparse realistic raindrop distribution

        float xCenter = 0.25 + 0.5 * r.y;
        float dx = abs(f.x - xCenter);
        float streakWidth = 0.065;
        float xProfile = smoothstep(streakWidth, 0.0, dx);
        // Elongated vertical teardrop motion trail
        float yProfile = smoothstep(0.02, 0.25, f.y) * smoothstep(0.96, 0.25, f.y);
        return xProfile * yProfile * (0.45 + 0.55 * r.y);
    }

    float3 sanitizeHDR(float3 c)
    {
        return float3(
            (c.r >= 0.0 && c.r <= 12.0) ? c.r : 0.0,
            (c.g >= 0.0 && c.g <= 12.0) ? c.g : 0.0,
            (c.b >= 0.0 && c.b <= 12.0) ? c.b : 0.0
        );
    }

    // Pass 0: Soft-knee HDR Bloom Prefilter
    fixed4 frag_prefilter(v2f_img i) : SV_Target
    {
        float3 c = sanitizeHDR(tex2D(_MainTex, i.uv).rgb) * _Exposure;
        float br = max(c.r, max(c.g, c.b));
        float knee = _BloomThreshold * 0.5 + 1e-4;
        float soft = clamp(br - _BloomThreshold + knee, 0.0, 2.0 * knee);
        soft = (soft * soft) / (4.0 * knee + 1e-4);
        float contrib = max(soft, br - _BloomThreshold) / max(br, 1e-4);
        return float4(sanitizeHDR(c * contrib), 1.0);
    }

    // Pass 1: 9-tap Separable Gaussian Blur
    fixed4 frag_blur(v2f_img i) : SV_Target
    {
        float2 off = _MainTex_TexelSize.xy * _BlurDir.xy;
        float3 sum = sanitizeHDR(tex2D(_MainTex, i.uv).rgb) * 0.227027;
        sum += sanitizeHDR(tex2D(_MainTex, i.uv + off * 1.384615).rgb) * 0.316216;
        sum += sanitizeHDR(tex2D(_MainTex, i.uv - off * 1.384615).rgb) * 0.316216;
        sum += sanitizeHDR(tex2D(_MainTex, i.uv + off * 3.230769).rgb) * 0.070270;
        sum += sanitizeHDR(tex2D(_MainTex, i.uv - off * 3.230769).rgb) * 0.070270;
        return float4(sanitizeHDR(sum), 1.0);
    }

    float3 ACESFilm(float3 x)
    {
        float a = 2.51f;
        float b = 0.03f;
        float c = 2.43f;
        float d = 0.59f;
        float e = 0.14f;
        return saturate((x * (a * x + b)) / (x * (c * x + d) + e));
    }

    // Pass 2: Master Composite (SSAO + SSR Puddle Reflections + Volumetric Fog + 3-Layer Lit Rain + Bloom + ACES)
    fixed4 frag_composite(v2f_img i) : SV_Target
    {
        float2 uv = i.uv;
        float2 centered = uv - 0.5;
        float dist2 = dot(centered, centered);

        // Subtle radial chromatic aberration at screen edges
        float2 caOffset = centered * dist2 * 0.0045;
        float3 col;
        col.r = sanitizeHDR(tex2D(_MainTex, uv + caOffset).rgb).r;
        col.g = sanitizeHDR(tex2D(_MainTex, uv).rgb).g;
        col.b = sanitizeHDR(tex2D(_MainTex, uv - caOffset).rgb).b;
        col *= _Exposure;

        // Depth & World Position reconstruction
        float rawDepth = SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, uv);
        float lin01 = Linear01Depth(rawDepth);
        float eyeDepth = max(0.1, LinearEyeDepth(rawDepth));

        float tanHalfFov = max(0.1, _CamFrustumParams.x);
        float aspect = max(0.1, _CamFrustumParams.y);
        float2 ndc = uv * 2.0 - 1.0;
        float3 viewRay = _CamForward + _CamRight * (ndc.x * aspect * tanHalfFov) + _CamUp * (ndc.y * tanHalfFov);
        float3 worldPos = _CamPos + viewRay * eyeDepth;
        float3 viewDir = normalize(worldPos - _CamPos);

        // Decode view-space normal and transform to world-space normal
        float4 dn = tex2D(_CameraDepthNormalsTexture, uv);
        float viewDepthDecoded;
        float3 viewNormal;
        DecodeDepthNormal(dn, viewDepthDecoded, viewNormal);
        float3 worldNormal = normalize(_CamRight * viewNormal.x + _CamUp * viewNormal.y - _CamForward * viewNormal.z + float3(0, 1e-5, 0));

        // 12-tap Multi-Scale Normal-Aware Screen-Space Ambient Occlusion (SSAO)
        float ao = 0.0;
        if (lin01 < 0.99)
        {
            float2 baseRad = _MainTex_TexelSize.xy * clamp(16.0 / max(1.0, eyeDepth * 0.50), 1.8, 12.0);
            float2 offsets[12] = {
                float2(1.0, 0.0), float2(-1.0, 0.0), float2(0.0, 1.0), float2(0.0, -1.0),
                float2(0.707, 0.707), float2(-0.707, 0.707), float2(0.707, -0.707), float2(-0.707, -0.707),
                float2(0.38, 0.16), float2(-0.38, -0.16), float2(-0.16, 0.38), float2(0.16, -0.38)
            };
            for (int k = 0; k < 12; k++)
            {
                float2 sampleUV = uv + offsets[k] * baseRad;
                float sd = LinearEyeDepth(SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, sampleUV));
                float4 sdn = tex2D(_CameraDepthNormalsTexture, sampleUV);
                float sViewDepth;
                float3 sViewNormal;
                DecodeDepthNormal(sdn, sViewDepth, sViewNormal);

                float diff = eyeDepth - sd;
                float normCrevice = saturate(1.0 - dot(viewNormal, sViewNormal));
                if (diff > 0.015 && diff < 0.85)
                {
                    float rangeCheck = smoothstep(0.85, 0.15, diff);
                    ao += (0.75 + 0.55 * normCrevice) * rangeCheck;
                }
                else if (abs(diff) <= 0.08)
                {
                    ao += normCrevice * 0.45;
                }
            }
            ao = saturate(1.0 - (ao / 12.0) * _AOIntensity * 1.15);
        }
        else
        {
            ao = 1.0;
        }
        col *= ao;

        float t = _Time.y + 4.25;
        float3 bloomSample = sanitizeHDR(tex2D(_BloomTex, uv).rgb);

        // --- COMMERCIAL-GRADE SCREEN-SPACE PUDDLE REFLECTIONS (SSR) & GROUND SPLASHES ---
        float upness = saturate((worldNormal.y - 0.68) * 3.5);
        if (upness > 0.01 && eyeDepth < 38.0 && lin01 < 0.98)
        {
            float pMask = puddleFBM(worldPos.xz);
            float roadCenter = saturate(1.0 - abs(worldPos.x) * 0.36) * 0.16;
            float puddle = smoothstep(0.42, 0.66, pMask + roadCenter) * upness;

            float3 ripSplash = computeRipplesAndSplashes(worldPos.xz, t);
            float2 rippleGrad = ripSplash.xy * (0.095 * puddle * puddle);
            float splashCrown = ripSplash.z * upness * saturate(1.0 - eyeDepth / 15.0);

            // Perturbed water normal in world space
            float3 waterN = normalize(float3(rippleGrad.x, 1.0, rippleGrad.y));
            float3 reflDir = reflect(viewDir, waterN);
            reflDir.y = max(0.08, reflDir.y);

            // Multi-step screen-space ray march along reflected vector
            float3 reflAccum = float3(0, 0, 0);
            float weightSum = 0.0;
            float stepDists[6] = { 1.4, 2.8, 4.6, 7.0, 10.2, 14.5 };
            for (int s = 0; s < 6; s++)
            {
                float3 sampleWPos = worldPos + reflDir * stepDists[s];
                float2 reflUV;
                if (projectWorldToScreen(sampleWPos, reflUV))
                {
                    reflUV = clamp(reflUV + rippleGrad * 0.12, 0.01, 0.99);
                    float sampleDepth = LinearEyeDepth(SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, reflUV));
                    if (sampleDepth > eyeDepth * 0.85)
                    {
                        float3 sCol = sanitizeHDR(tex2D(_MainTex, reflUV).rgb) * _Exposure;
                        float3 sBloom = sanitizeHDR(tex2D(_BloomTex, reflUV).rgb) * 1.65;
                        float lum = dot(sCol + sBloom, float3(0.299, 0.587, 0.114));
                        float w = 1.0 + lum * 2.5;
                        reflAccum += (sCol * 0.75 + sBloom) * w;
                        weightSum += w;
                    }
                }
            }

            if (weightSum > 0.01)
            {
                float3 reflColor = reflAccum / weightSum;
                float ndotv = saturate(dot(-viewDir, waterN));
                float fresnel = pow(max(0.0, 1.0 - ndotv), 3.2);
                float reflStrength = saturate((0.18 + 0.82 * puddle) * (0.28 + 0.72 * fresnel)) * _ReflectionIntensity;
                col = lerp(col, reflColor * 0.95 + col * 0.25, reflStrength);
            }

            // Glistening raindrop impact micro-splashes on wet asphalt & puddles
            float3 localLight = bloomSample + float3(0.18, 0.24, 0.32);
            col += localLight * splashCrown * 0.55 * _RainIntensity;
        }

        // --- DEPTH-BASED VOLUMETRIC NIGHT MIST ---
        float fogFactor = saturate(1.0 - exp(-pow(max(0.0, eyeDepth * _FogDensity), 1.35)));
        if (lin01 > 0.995) fogFactor = 0.88;
        float3 fogCol = lerp(_FogColorNear.rgb, _FogColorFar.rgb, saturate(eyeDepth / 34.0));
        fogCol += bloomSample * 0.38;
        col = lerp(col, fogCol, fogFactor);

        // --- 3-LAYER LIT CINEMATIC RAIN SHEET ---
        if (_RainIntensity > 0.01)
        {
            float rainNear = (eyeDepth > 1.8) ? evalRainStreakLayer(uv, 34.0, 4.2, 4.8, 0.06, 11.7, t) : 0.0;
            float rainMid  = (eyeDepth > 4.8) ? evalRainStreakLayer(uv, 62.0, 7.5, 5.6, 0.07, 29.3, t) : 0.0;
            float rainFar  = (eyeDepth > 9.5) ? evalRainStreakLayer(uv, 105.0, 12.0, 6.4, 0.08, 53.1, t) : 0.0;

            float totalRain = (rainNear * 0.52 + rainMid * 0.34 + rainFar * 0.22) * _RainIntensity;
            float3 rainLight = float3(0.24, 0.32, 0.42) + bloomSample * 2.15;
            col += rainLight * totalRain * 0.48;
        }

        // Add soft HDR Bloom halation
        col += bloomSample * _BloomIntensity;

        // Subtle cool night-horror color grading & ACES Filmic Tonemapping
        col = sanitizeHDR(col) * float3(0.96, 0.99, 1.05);
        col = ACESFilm(col);

        // Cinematic Vignette
        float vig = saturate(1.0 - dist2 * _VignetteIntensity * 2.3);
        col *= pow(max(0.0, vig), 1.25);

        // Subtle Analog Film Grain
        float grain = (hash12(uv * 1024.0 + frac(_Time.y) * 137.0) - 0.5) * _GrainIntensity;
        col = saturate(col + grain);

        return float4(col, 1.0);
    }
    ENDCG

    SubShader
    {
        Cull Off ZWrite Off ZTest Always

        Pass
        {
            CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment frag_prefilter
            ENDCG
        }

        Pass
        {
            CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment frag_blur
            ENDCG
        }

        Pass
        {
            CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment frag_composite
            ENDCG
        }
    }
}
