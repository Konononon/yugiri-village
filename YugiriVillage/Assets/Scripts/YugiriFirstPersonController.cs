using UnityEngine;

namespace Yugiri.Gameplay
{
    [RequireComponent(typeof(CharacterController))]
    public class YugiriFirstPersonController : MonoBehaviour
    {
        [Header("Movement")]
        public float walkSpeed = 2.65f;
        public float sprintSpeed = 4.25f;
        public float gravity = -16.0f;
        public float mouseSensitivity = 1.85f;

        [Header("Camera & Headbob")]
        public Camera playerCamera;
        public float eyeHeight = 1.66f;
        public float bobFrequency = 1.85f;
        public float bobHorizontalAmplitude = 0.024f;
        public float bobVerticalAmplitude = 0.034f;
        public float normalFov = 62f;
        public float zoomFov = 40f;

        [Header("Flashlight")]
        public Light flashlightSpot;
        public Light flashlightSpill;
        public AudioClip flashlightClickClip;

        [Header("Audio")]
        public AudioSource footstepSource;
        public AudioSource sfxSource;
        public AudioClip[] wetAsphaltSteps;
        public AudioClip[] stoneSteps;

        private CharacterController _cc;
        private float _pitch = 0f;
        private float _verticalVel = 0f;
        private float _bobTimer = 0f;
        private float _stepCycle = 0f;
        private int _lastStepIdx = -1;
        private bool _flashlightOn = true;
        private Quaternion _flashlightLagRot;

        // UI / Narrative state
        private YugiriInteractable _hoveredInteractable;
        private string _activeSubtitle = "";
        private string _activeTitle = "";
        private float _subtitleTimer = 0f;
        private float _introFade = 1.0f;
        private bool _cursorLocked = true;

        private GUIStyle _promptStyle;
        private GUIStyle _subtitleBoxStyle;
        private GUIStyle _titleStyle;
        private GUIStyle _hudHintStyle;
        private Texture2D _darkTex;

        private void Start()
        {
            _cc = GetComponent<CharacterController>();
            if (playerCamera == null)
            {
                playerCamera = GetComponentInChildren<Camera>();
            }
            if (playerCamera != null)
            {
                _flashlightLagRot = playerCamera.transform.rotation;
            }

            LockCursor(true);
            ShowSubtitle("유우기리 마을 (夕霧村) — 밤 11시 45분", "마지막 버스는 오지 않았다. 안개에 잠긴 골목을 따라 언덕 위 신사로 향해야 한다.", 7.5f);
        }

        private void LockCursor(bool locked)
        {
            _cursorLocked = locked;
            Cursor.lockState = locked ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !locked;
        }

        private void Update()
        {
            if (Input.GetKeyDown(KeyCode.Escape))
            {
                LockCursor(!_cursorLocked);
            }
            if (!_cursorLocked && Input.GetMouseButtonDown(0))
            {
                LockCursor(true);
            }

            if (_introFade > 0f)
            {
                _introFade = Mathf.Max(0f, _introFade - Time.deltaTime * 0.45f);
            }
            if (_subtitleTimer > 0f)
            {
                _subtitleTimer -= Time.deltaTime;
            }

            HandleLook();
            HandleMovementAndBob();
            HandleFlashlight();
            HandleInteraction();
        }

        private void HandleLook()
        {
            if (!_cursorLocked || playerCamera == null) return;

            float mx = Input.GetAxisRaw("Mouse X") * mouseSensitivity;
            float my = Input.GetAxisRaw("Mouse Y") * mouseSensitivity;

            transform.Rotate(Vector3.up * mx);
            _pitch = Mathf.Clamp(_pitch - my, -78f, 78f);
            playerCamera.transform.localRotation = Quaternion.Euler(_pitch, 0f, 0f);

            // Smooth focus zoom on Right Mouse Button
            float targetFov = Input.GetMouseButton(1) ? zoomFov : normalFov;
            playerCamera.fieldOfView = Mathf.Lerp(playerCamera.fieldOfView, targetFov, Time.deltaTime * 8f);
        }

        private void HandleMovementAndBob()
        {
            float hx = Input.GetAxisRaw("Horizontal");
            float vz = Input.GetAxisRaw("Vertical");
            Vector3 inputDir = (transform.right * hx + transform.forward * vz).normalized;

            bool sprinting = Input.GetKey(KeyCode.LeftShift);
            float speed = sprinting ? sprintSpeed : walkSpeed;

            if (_cc.isGrounded && _verticalVel < 0f)
            {
                _verticalVel = -2.0f;
            }
            _verticalVel += gravity * Time.deltaTime;

            Vector3 velocity = inputDir * speed + Vector3.up * _verticalVel;
            _cc.Move(velocity * Time.deltaTime);

            Vector3 horizVel = new Vector3(_cc.velocity.x, 0f, _cc.velocity.z);
            float moveMag = horizVel.magnitude;

            if (playerCamera != null)
            {
                if (moveMag > 0.2f && _cc.isGrounded)
                {
                    float freq = bobFrequency * (sprinting ? 1.38f : 1.0f);
                    _bobTimer += Time.deltaTime * freq * Mathf.PI * 2f;
                    float bx = Mathf.Cos(_bobTimer * 0.5f) * bobHorizontalAmplitude;
                    float by = Mathf.Sin(_bobTimer) * bobVerticalAmplitude;
                    playerCamera.transform.localPosition = Vector3.Lerp(
                        playerCamera.transform.localPosition,
                        new Vector3(bx, eyeHeight + by, 0f),
                        Time.deltaTime * 12f
                    );

                    _stepCycle += Time.deltaTime * freq;
                    if (_stepCycle >= 1.0f)
                    {
                        _stepCycle -= 1.0f;
                        PlayFootstep(sprinting ? 0.85f : 0.62f);
                    }
                }
                else
                {
                    // Subtle breathing sway when standing still
                    float breath = Mathf.Sin(Time.time * 1.4f) * 0.008f;
                    playerCamera.transform.localPosition = Vector3.Lerp(
                        playerCamera.transform.localPosition,
                        new Vector3(0f, eyeHeight + breath, 0f),
                        Time.deltaTime * 6f
                    );
                }
            }
        }

        private void PlayFootstep(float volume)
        {
            if (footstepSource == null) return;
            // Detect whether on stone shrine stairs/courtyard (Z > 19.5m) or wet asphalt alley
            bool onStone = transform.position.z > 19.5f;
            AudioClip[] pool = (onStone && stoneSteps != null && stoneSteps.Length > 0) ? stoneSteps : wetAsphaltSteps;
            if (pool == null || pool.Length == 0) return;

            int idx = Random.Range(0, pool.Length);
            if (pool.Length > 1 && idx == _lastStepIdx)
            {
                idx = (idx + 1) % pool.Length;
            }
            _lastStepIdx = idx;
            footstepSource.pitch = Random.Range(0.93f, 1.07f);
            footstepSource.PlayOneShot(pool[idx], volume);
        }

        private void HandleFlashlight()
        {
            if (Input.GetKeyDown(KeyCode.F))
            {
                _flashlightOn = !_flashlightOn;
                if (flashlightSpot != null) flashlightSpot.enabled = _flashlightOn;
                if (flashlightSpill != null) flashlightSpill.enabled = _flashlightOn;
                if (sfxSource != null && flashlightClickClip != null)
                {
                    sfxSource.PlayOneShot(flashlightClickClip, 0.8f);
                }
            }

            if (flashlightSpot != null && playerCamera != null)
            {
                _flashlightLagRot = Quaternion.Slerp(_flashlightLagRot, playerCamera.transform.rotation, Time.deltaTime * 14f);
                flashlightSpot.transform.rotation = _flashlightLagRot;
            }
        }

        private void HandleInteraction()
        {
            _hoveredInteractable = null;
            if (playerCamera == null) return;

            Ray ray = new Ray(playerCamera.transform.position, playerCamera.transform.forward);
            if (Physics.Raycast(ray, out RaycastHit hit, 3.4f))
            {
                _hoveredInteractable = hit.collider.GetComponentInParent<YugiriInteractable>();
            }

            if (_hoveredInteractable != null && (Input.GetKeyDown(KeyCode.E) || Input.GetMouseButtonDown(0)))
            {
                ShowSubtitle(_hoveredInteractable.titleJp, _hoveredInteractable.inspectDialogue, 7.0f);
                if (sfxSource != null)
                {
                    if (_hoveredInteractable.interactSfx != null)
                        sfxSource.PlayOneShot(_hoveredInteractable.interactSfx, 0.9f);
                    if (_hoveredInteractable.horrorStingerSfx != null)
                        sfxSource.PlayOneShot(_hoveredInteractable.horrorStingerSfx, 0.75f);
                }

                if (_hoveredInteractable.triggersShrineEvent)
                {
                    foreach (YugiriLightFlicker fl in FindObjectsByType<YugiriLightFlicker>(FindObjectsSortMode.None))
                    {
                        Light l = fl.GetComponent<Light>();
                        if (l != null && fl.style == YugiriLightFlicker.FlickerStyle.CandleFlame)
                        {
                            l.color = new Color(1.0f, 0.22f, 0.14f);
                            fl.baseIntensity = 2.8f;
                        }
                    }
                }
            }
        }

        public void ShowSubtitle(string title, string body, float duration)
        {
            _activeTitle = title;
            _activeSubtitle = body;
            _subtitleTimer = duration;
        }

        private void InitStyles()
        {
            if (_darkTex == null)
            {
                _darkTex = new Texture2D(1, 1);
                _darkTex.SetPixel(0, 0, new Color(0.02f, 0.03f, 0.04f, 0.78f));
                _darkTex.Apply();
            }

            if (_promptStyle == null)
            {
                _promptStyle = new GUIStyle(GUI.skin.label)
                {
                    alignment = TextAnchor.MiddleCenter,
                    fontSize = 16,
                    fontStyle = FontStyle.Bold
                };
                _promptStyle.normal.textColor = new Color(0.92f, 0.90f, 0.84f, 0.95f);
            }

            if (_titleStyle == null)
            {
                _titleStyle = new GUIStyle(GUI.skin.label)
                {
                    alignment = TextAnchor.MiddleCenter,
                    fontSize = 18,
                    fontStyle = FontStyle.Bold
                };
                _titleStyle.normal.textColor = new Color(0.88f, 0.32f, 0.26f, 1.0f);
            }

            if (_subtitleBoxStyle == null)
            {
                _subtitleBoxStyle = new GUIStyle(GUI.skin.box)
                {
                    alignment = TextAnchor.MiddleCenter,
                    fontSize = 16,
                    wordWrap = true,
                    padding = new RectOffset(22, 22, 14, 14)
                };
                _subtitleBoxStyle.normal.background = _darkTex;
                _subtitleBoxStyle.normal.textColor = new Color(0.94f, 0.93f, 0.89f, 1.0f);
            }

            if (_hudHintStyle == null)
            {
                _hudHintStyle = new GUIStyle(GUI.skin.label)
                {
                    alignment = TextAnchor.UpperLeft,
                    fontSize = 13
                };
                _hudHintStyle.normal.textColor = new Color(0.75f, 0.80f, 0.84f, 0.65f);
            }
        }

        private void OnGUI()
        {
            InitStyles();

            // Center minimal reticle dot
            float cx = Screen.width * 0.5f;
            float cy = Screen.height * 0.5f;
            GUI.color = _hoveredInteractable != null ? new Color(1f, 0.45f, 0.35f, 0.9f) : new Color(1f, 1f, 1f, 0.35f);
            float dotSize = _hoveredInteractable != null ? 6f : 3f;
            GUI.DrawTexture(new Rect(cx - dotSize * 0.5f, cy - dotSize * 0.5f, dotSize, dotSize), Texture2D.whiteTexture);
            GUI.color = Color.white;

            // Hover prompt
            if (_hoveredInteractable != null)
            {
                GUI.Label(new Rect(cx - 220f, cy + 18f, 440f, 28f), $"{_hoveredInteractable.titleJp}  —  {_hoveredInteractable.promptText}", _promptStyle);
            }

            // Subtitle narrative box
            if (_subtitleTimer > 0f && !string.IsNullOrEmpty(_activeSubtitle))
            {
                float alpha = Mathf.Clamp01(_subtitleTimer * 1.2f);
                GUI.color = new Color(1f, 1f, 1f, alpha);
                float bw = Mathf.Min(760f, Screen.width - 80f);
                float bh = 96f;
                Rect boxRect = new Rect((Screen.width - bw) * 0.5f, Screen.height - bh - 42f, bw, bh);
                GUI.Box(boxRect, "", _subtitleBoxStyle);
                GUI.Label(new Rect(boxRect.x, boxRect.y + 10f, boxRect.width, 26f), _activeTitle, _titleStyle);
                GUI.Label(new Rect(boxRect.x + 20f, boxRect.y + 36f, boxRect.width - 40f, 52f), _activeSubtitle, _promptStyle);
                GUI.color = Color.white;
            }

            // Top-left minimal controls guide
            GUI.Label(
                new Rect(18f, 14f, 460f, 48f),
                "夕霧村 (YUGIRI VILLAGE)\n[WASD] 이동  |  [Shift] 달리기  |  [F] 손전등  |  [우클릭] 집중  |  [E] 조사",
                _hudHintStyle
            );

            if (_introFade > 0f)
            {
                GUI.color = new Color(0f, 0f, 0f, _introFade);
                GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), Texture2D.whiteTexture);
                GUI.color = Color.white;
            }
        }
    }
}
