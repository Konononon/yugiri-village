Shader "Custom/YugiriVolumetricCone"
{
    Properties
    {
        [HDR] _Color ("Volumetric Tint", Color) = (1.0, 0.72, 0.38, 0.14)
        _SoftFade ("Depth Softness", Float) = 1.2
    }
    SubShader
    {
        Tags { "Queue"="Transparent+20" "IgnoreProjector"="True" "RenderType"="Transparent" }
        Blend SrcAlpha One
        ZWrite Off
        Cull Back

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 worldNormal : TEXCOORD1;
                float3 worldPos : TEXCOORD2;
                float4 screenPos : TEXCOORD3;
            };

            float4 _Color;
            float _SoftFade;
            sampler2D _CameraDepthTexture;

            v2f vert(appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                o.worldNormal = UnityObjectToWorldNormal(v.normal);
                o.worldPos = mul(unity_ObjectToWorld, v.vertex).xyz;
                o.screenPos = ComputeScreenPos(o.pos);
                COMPUTE_EYEDEPTH(o.screenPos.z);
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float3 V = normalize(_WorldSpaceCameraPos - i.worldPos);
                float3 N = normalize(i.worldNormal);

                // Soft Fresnel edge attenuation so cone silhouette is completely seamless
                float ndotv = abs(dot(N, V));
                float edgeFade = pow(ndotv, 1.85);

                // Vertical attenuation from lamp apex (uv.y = 1) down to ground (uv.y = 0)
                float vertFade = pow(saturate(i.uv.y), 0.75) * smoothstep(1.0, 0.82, i.uv.y) * smoothstep(0.0, 0.35, i.uv.y);

                // Soft depth intersection fade against scene geometry
                float sceneZ = LinearEyeDepth(SAMPLE_DEPTH_TEXTURE_PROJ(_CameraDepthTexture, UNITY_PROJ_COORD(i.screenPos)));
                float partZ = i.screenPos.z;
                float depthFade = saturate((sceneZ - partZ) * _SoftFade);

                // Subtle distance fade when camera is right inside the cone
                float camDist = length(_WorldSpaceCameraPos - i.worldPos);
                float nearCamFade = smoothstep(0.6, 2.2, camDist);

                float alpha = _Color.a * edgeFade * vertFade * depthFade * nearCamFade;
                return fixed4(_Color.rgb, saturate(alpha));
            }
            ENDCG
        }
    }
}
