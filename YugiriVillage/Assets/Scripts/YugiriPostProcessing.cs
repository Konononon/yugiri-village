using UnityEngine;

namespace Yugiri.Gameplay
{
    [ExecuteAlways]
    [RequireComponent(typeof(Camera))]
    [ImageEffectAllowedInSceneView]
    public class YugiriPostProcessing : MonoBehaviour
    {
        public Shader postShader;
        [Range(0.005f, 0.08f)] public float fogDensity = 0.024f;
        public Color fogColorNear = new Color(0.055f, 0.082f, 0.115f, 1f);
        public Color fogColorFar = new Color(0.020f, 0.032f, 0.052f, 1f);
        [Range(0f, 2f)] public float bloomIntensity = 0.68f;
        [Range(0.1f, 1.5f)] public float bloomThreshold = 0.58f;
        [Range(0f, 1f)] public float vignetteIntensity = 0.42f;
        [Range(0f, 0.08f)] public float grainIntensity = 0.016f;
        [Range(0f, 1f)] public float aoIntensity = 0.65f;
        [Range(0.5f, 2.5f)] public float exposure = 1.16f;
        [Range(0f, 1.5f)] public float reflectionIntensity = 0.88f;
        [Range(0f, 1.5f)] public float rainIntensity = 0.92f;

        private Material _mat;
        private Camera _cam;

        private void OnEnable()
        {
            _cam = GetComponent<Camera>();
            if (_cam != null)
            {
                _cam.depthTextureMode |= DepthTextureMode.Depth | DepthTextureMode.DepthNormals;
                _cam.allowHDR = true;
            }
        }

        private void EnsureMaterial()
        {
            if (postShader == null)
            {
                postShader = Shader.Find("Hidden/YugiriHorrorPostFX");
            }
            if (_mat == null && postShader != null && postShader.isSupported)
            {
                _mat = new Material(postShader) { hideFlags = HideFlags.HideAndDontSave };
            }
        }

        private void OnRenderImage(RenderTexture source, RenderTexture destination)
        {
            EnsureMaterial();
            if (_mat == null)
            {
                Graphics.Blit(source, destination);
                return;
            }

            if (_cam == null) _cam = GetComponent<Camera>();
            if (_cam != null)
            {
                _cam.depthTextureMode |= DepthTextureMode.Depth | DepthTextureMode.DepthNormals;
                float tanHalfFov = Mathf.Tan(_cam.fieldOfView * 0.5f * Mathf.Deg2Rad);
                float aspect = (float)source.width / Mathf.Max(1, source.height);
                _mat.SetVector("_CamPos", _cam.transform.position);
                _mat.SetVector("_CamForward", _cam.transform.forward);
                _mat.SetVector("_CamRight", _cam.transform.right);
                _mat.SetVector("_CamUp", _cam.transform.up);
                _mat.SetVector("_CamFrustumParams", new Vector4(tanHalfFov, aspect, _cam.nearClipPlane, _cam.farClipPlane));
            }

            _mat.SetColor("_FogColorNear", fogColorNear);
            _mat.SetColor("_FogColorFar", fogColorFar);
            _mat.SetFloat("_FogDensity", fogDensity);
            _mat.SetFloat("_BloomIntensity", bloomIntensity);
            _mat.SetFloat("_BloomThreshold", bloomThreshold);
            _mat.SetFloat("_VignetteIntensity", vignetteIntensity);
            _mat.SetFloat("_GrainIntensity", grainIntensity);
            _mat.SetFloat("_AOIntensity", aoIntensity);
            _mat.SetFloat("_Exposure", exposure);
            _mat.SetFloat("_ReflectionIntensity", reflectionIntensity);
            _mat.SetFloat("_RainIntensity", rainIntensity);

            int tw = Mathf.Max(1, source.width / 2);
            int th = Mathf.Max(1, source.height / 2);
            RenderTextureFormat fmt = source.format;

            RenderTexture rtPrefilter = RenderTexture.GetTemporary(tw, th, 0, fmt);
            RenderTexture rtBlur1 = RenderTexture.GetTemporary(tw / 2, th / 2, 0, fmt);
            RenderTexture rtBlur2 = RenderTexture.GetTemporary(tw / 2, th / 2, 0, fmt);

            // Pass 0: Prefilter bright HDR regions
            Graphics.Blit(source, rtPrefilter, _mat, 0);
            Graphics.Blit(rtPrefilter, rtBlur1);

            // Two iterations of separable Gaussian blur for wide soft halation
            for (int i = 0; i < 2; i++)
            {
                _mat.SetVector("_BlurDir", new Vector4(1.5f + i, 0f, 0f, 0f));
                Graphics.Blit(rtBlur1, rtBlur2, _mat, 1);
                _mat.SetVector("_BlurDir", new Vector4(0f, 1.5f + i, 0f, 0f));
                Graphics.Blit(rtBlur2, rtBlur1, _mat, 1);
            }

            _mat.SetTexture("_BloomTex", rtBlur1);
            Graphics.Blit(source, destination, _mat, 2);

            RenderTexture.ReleaseTemporary(rtPrefilter);
            RenderTexture.ReleaseTemporary(rtBlur1);
            RenderTexture.ReleaseTemporary(rtBlur2);
        }

        private void OnDisable()
        {
            if (_mat != null)
            {
                DestroyImmediate(_mat);
                _mat = null;
            }
        }
    }
}
