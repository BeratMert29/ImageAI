import streamlit as st
import os
import base64
import time
from google.oauth2 import service_account
import vertexai
from vertexai.preview.vision_models import ImageGenerationModel
from vertexai.generative_models import GenerativeModel, Part
from google import genai
from google.genai import types
import logging
from io import BytesIO
import certifi
import tempfile
import threading
from pathlib import Path
from PIL import Image
import io

# --- Configuration ---
PROJECT_ID = "your_project_id"
LOCATION = "project_account_location"
script_dir = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_PATH = r"your service account path"
IMAGEN_MODEL_NAME = "imagen-4.0-generate-001"
GEMINI_MODEL_NAME = "gemini-2.5-flash"
VIDEO_MODEL_NAME = "veo-3.0-generate-preview"
client = None

# --- Load External CSS ---
def load_css():
    """Load external CSS file"""
    css_file = os.path.join(script_dir, "style.css")
    if os.path.exists(css_file):
        with open(css_file) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    else:
        st.warning("CSS file not found. Using default styling.")

# --- Utility Functions ---
def downscale_image_for_display(pil_image, target_width: int):
    try:
        width, height = pil_image.size
        if width <= target_width:
            return pil_image
        target_height = int(height * (target_width / float(width)))
        return pil_image.resize((target_width, target_height), resample=Image.LANCZOS)
    except Exception:
        return pil_image

# --- Authentication Functions ---
@st.cache_resource
def authenticate_and_initialize():
    """Authenticate with Google Cloud and initialize Vertex AI."""
    try: 
        if not os.path.exists(SERVICE_ACCOUNT_PATH):
            st.error(f"Error: Service account file not found at '{SERVICE_ACCOUNT_PATH}'")
            st.stop()
        
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_PATH,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SERVICE_ACCOUNT_PATH
        os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID

        vertexai.init(
            project=PROJECT_ID,
            location=LOCATION,
            credentials=credentials
        )
        
        global client
        if client is None:
            client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
        
        return True
        
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        st.stop()

@st.cache_resource
def create_imagen_model():
    """Create and return Imagen model instance."""
    try:
        model = ImageGenerationModel.from_pretrained(IMAGEN_MODEL_NAME)
        return model
    except Exception as e:
        st.error(f"Failed to load {IMAGEN_MODEL_NAME}: {str(e)}")
        st.stop()

@st.cache_resource
def create_gemini_model():
    """Create and return Gemini model instance."""
    try:
        model = GenerativeModel(GEMINI_MODEL_NAME)
        return model
    except Exception as e:
        st.error(f"Failed to load {GEMINI_MODEL_NAME}: {str(e)}")
        st.stop()

@st.cache_resource
def create_veo_model():
    """Create and return VEO model instance."""
    try:
        model = GenerativeModel(VIDEO_MODEL_NAME)
        return model
    except Exception as e:
        st.error(f"Failed to load {VIDEO_MODEL_NAME}: {str(e)}")
        st.stop()

def generate_video_from_image(image_bytes, prompt):
    """Generate a video using Veo with optional image + text prompt."""
    try:
        global client
        if client is None:
            if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") != SERVICE_ACCOUNT_PATH:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SERVICE_ACCOUNT_PATH
            if os.environ.get("GOOGLE_CLOUD_PROJECT") != PROJECT_ID:
                os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
            
            client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

        generate_kwargs = {
            "prompt": prompt,
            "model": VIDEO_MODEL_NAME,
        }
        
        video_bytes = None
        
        if image_bytes is not None:
            try:
                image = Image.open(io.BytesIO(image_bytes))
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='JPEG', quality=95)
                img_byte_arr = img_byte_arr.getvalue()
                
                image_obj = types.Image(image_bytes=img_byte_arr, mime_type="image/jpeg")
                generate_kwargs["image"] = image_obj
                
            except Exception as e:
                st.error(f"❌ Failed to process reference image: {e}")
                return None
        
        generate_kwargs["config"] = types.GenerateVideosConfig(
            aspect_ratio="16:9",
            number_of_videos=1,
            duration_seconds=8,
            resolution="1080p",
            person_generation="allow_adult",
            enhance_prompt=True,
            generate_audio=True,
        )
        
        try:
            operation = client.models.generate_videos(**generate_kwargs)
        except TypeError as e:
            st.error(f"TypeError: {e}")
        
        while not operation.done:
            time.sleep(45)
            operation = client.operations.get(operation)

        if operation.response:
            if hasattr(operation.response, 'generated_videos') and len(operation.response.generated_videos) > 0:
                video_obj = operation.response.generated_videos[0]
                if hasattr(video_obj, 'video') and hasattr(video_obj.video, 'video_bytes'):
                    video_bytes = video_obj.video.video_bytes
            
            if video_bytes is not None:
                if isinstance(video_bytes, bytes) and video_bytes.startswith(b'AAAA'):
                    return base64.b64decode(video_bytes)
                return video_bytes
            
            return operation

    except Exception as e:
        st.error(f"❌ Video generation request failed: {e}")
        return None

# --- Main App ---
def main():
    # Page configuration
    st.set_page_config(
        page_title="AI Content Generator",
        layout="wide",
        page_icon="🎨",
        initial_sidebar_state="collapsed"
    )

    # Load external CSS
    load_css()

    # App header
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">AI Content Generator</h1>
        <p class="app-subtitle">Transform your ideas into stunning images and videos</p>
    </div>
    """, unsafe_allow_html=True)

    # Initialize session state
    if 'generated_image' not in st.session_state:
        st.session_state.generated_image = None
    if 'current_prompt' not in st.session_state:
        st.session_state.current_prompt = ""
    if 'final_prompt' not in st.session_state:
        st.session_state.final_prompt = ""
    if 'negative_prompt' not in st.session_state:
        st.session_state.negative_prompt = ""
    if 'iteration_count' not in st.session_state:
        st.session_state.iteration_count = 0
    if 'favorites' not in st.session_state:
        st.session_state.favorites = []
    if 'generated_video' not in st.session_state:
        st.session_state.generated_video = None
    if 'video_iteration_count' not in st.session_state:
        st.session_state.video_iteration_count = 0

    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🖼️ Image Generation", "🎬 Video Generation", "⭐ Favorites", "🧪 Gemini Image Gen"])

    # Authenticate and initialize models
    if authenticate_and_initialize():
        imagen_model = create_imagen_model()
        gemini_model = create_gemini_model()
        veo_model = create_veo_model()
        
        # --- IMAGE GENERATION TAB ---
        with tab1:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown('''
            <div class="section-header">
                <div class="icon">🎨</div>
                <div>
                    <div>Image Generation</div>
                </div>
            </div>
            <div class="section-description">Create stunning images from text descriptions or reference images</div>
            ''', unsafe_allow_html=True)
            
            col_left, col_right = st.columns([2, 1])
            
            with col_left:
                st.markdown('<div class="input-group">', unsafe_allow_html=True)
                st.markdown('<div class="input-label">✍️ Image Prompt</div>', unsafe_allow_html=True)
                st.markdown('<div class="input-description">Describe the image you want to create</div>', unsafe_allow_html=True)
                prompt = st.text_area(
                    "Enter your image prompt:",
                    height=200,
                    placeholder="A futuristic cityscape at sunset, with flying cars and neon lights...",
                    key="prompt_input",
                    label_visibility="collapsed"
                )
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Style Choice Section
                st.markdown('<div class="input-group">', unsafe_allow_html=True)
                st.markdown('<div class="input-label">🎨 Image Style</div>', unsafe_allow_html=True)
                st.markdown('<div class="input-description">Choose the style that best fits your image purpose</div>', unsafe_allow_html=True)
                style_choice = st.selectbox(
                    "Select image style:",
                    ["E-commerce Product", "Real-world Lifestyle", "Creative Artistic"],
                    key="style_choice",
                    label_visibility="collapsed"
                )
                
                # Style descriptions
                style_descriptions = {
                    "E-commerce Product": "Clean, professional photos with studio lighting, neutral backgrounds, and commercial appeal - perfect for product catalogs and online retail.",
                    "Real-world Lifestyle": "Natural, authentic images showing products in everyday use with natural lighting and relatable settings - ideal for lifestyle marketing.",
                    "Creative Artistic": "Dramatic, artistic photos with creative lighting, artistic backgrounds, and artistic composition - great for creative campaigns and social media."
                }
                
                if style_choice in style_descriptions:
                    style_class = {
                        "E-commerce Product": "ecommerce",
                        "Real-world Lifestyle": "lifestyle", 
                        "Creative Artistic": "creative"
                    }.get(style_choice, "ecommerce")
                    
                    st.markdown(f'<div class="style-badge {style_class}">🎨 {style_choice}</div>', unsafe_allow_html=True)
                    st.info(f"💡 **{style_choice}**: {style_descriptions[style_choice]}")
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Negative Prompt Section
                st.markdown('<div class="input-group">', unsafe_allow_html=True)
                st.markdown('<div class="input-label">🚫 Negative Prompt</div>', unsafe_allow_html=True)
                st.markdown('<div class="input-description">Specify what you DON\'T want in the image</div>', unsafe_allow_html=True)
                negative_prompt = st.text_area(
                    "Negative prompt:",
                    height=80,
                    placeholder="blurry, distorted, low quality, text overlay, watermarks...",
                    key="negative_prompt_input",
                    label_visibility="collapsed"
                )
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col_right:
                st.markdown('<div class="input-group">', unsafe_allow_html=True)
                st.markdown('<div class="input-label">📁 Reference Image (Optional)</div>', unsafe_allow_html=True)
                st.markdown('<div class="input-description">Upload a product image to guide the AI generation</div>', unsafe_allow_html=True)
                reference_image_file = st.file_uploader(
                    "Choose an image file:",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="reference_upload",
                    label_visibility="collapsed"
                )
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Advanced Parameters
                st.markdown('<div class="input-group">', unsafe_allow_html=True)
                st.markdown('<div class="input-label">⚙️ Advanced Parameters</div>', unsafe_allow_html=True)
                adv_col1, adv_col2 = st.columns(2)
                with adv_col1:
                    num_images = st.slider(
                        "Number of images",
                        min_value=1,
                        max_value=4,
                        value=1,
                        key="num_images_selector",
                    )
                with adv_col2:
                    guidance_scale = st.slider(
                        "Guidance scale",
                        min_value=1.0,
                        max_value=20.0,
                        value=7.5,
                        step=0.5,
                        key="guidance_scale_selector",
                    )
                st.markdown('</div>', unsafe_allow_html=True)
                
                generate_clicked = st.button("✨ Generate Image", type="primary", key="generate_main")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Generation logic
            if generate_clicked:
                if not prompt and reference_image_file is None:
                    st.warning("Please either enter a prompt or upload a reference image to generate an image.")
                else:
                    final_prompt = prompt if prompt else ""
                    try:
                        # If a reference image is provided, use it to enhance the prompt
                        if reference_image_file is not None:
                            with st.spinner("Analyzing reference image..."):
                                st.image(reference_image_file, caption="Your Reference Image", width=300)
                                image_bytes = reference_image_file.getvalue()
                                mime_type = reference_image_file.type
                                image_part = Part.from_data(image_bytes, mime_type=mime_type)

                                # Style-specific description prompts
                                style_prompts = {
                                   "E-commerce Product": """You are an expert in e-commerce product imagery. Analyze the provided product image and generate ONE cohesive paragraph (150–250 words). 
Begin exactly with:

"Create a professional e commerce product image, showing the exact same product with all details preserved [add — specifically the \"<BRAND> <MODEL>\" — if you could read them], in a clean commercial photography style suitable for online retail,"

Constraints:
- Do NOT modify the product itself: preserve shape, proportions, dimensions, colors, materials, textures, logos, texts, branding elements, and surface finishes.
- Only modify the background, scene, lighting, or camera angle.
- Keep realistic shadows, reflections, and perspective.
- Product must stay centered, sharp, and in focus.

Style:
- Neutral or white background
- Studio lighting (soft key light, subtle rim light)
- Minimal clutter, catalog-ready composition
- Confident, precise wording: "exactly", "identical", "specifically", "not altered"
""",

    "Real-world Lifestyle": """You are a lifestyle photography expert. Analyze the provided product image and generate ONE cohesive paragraph (150–250 words). 
Begin exactly with:

"Create a realistic lifestyle image, showing the exact same product with all details preserved [add — specifically the \"<BRAND> <MODEL>\" — if you could read them], in a natural, everyday setting that demonstrates how people would actually use this product,"

Constraints:
- Preserve the product's physical features exactly: shape, size, colors, logos, branding, text, textures.
- Only adjust background, lighting, environment, or perspective.
- Keep natural shadows, realistic reflections, and perspective.

Style:
- Natural lighting (window light, outdoor ambient)
- Authentic home, office, or outdoor context
- Relatable props, warm atmosphere
- Composition must look natural, not staged
- Confident, precise wording: "exactly", "identical", "specifically", "not altered"
""",

    "Creative Artistic": """You are a creative photography expert. Analyze the provided product image and generate ONE cohesive paragraph (150–250 words). 
Begin exactly with:

"Create an artistic, creative image, showing the exact same product with all details preserved [add — specifically the \"<BRAND> <MODEL>\" — if you could read them], in a creative artistic style with dramatic lighting and artistic composition,"

Constraints:
- Preserve the product's features exactly: dimensions, materials, branding, text, logos.
- Do NOT alter or distort the product in any way.
- Only modify lighting, artistic background, composition, or camera angle.

Style:
- Dramatic or experimental lighting (shadows, colored gels, patterns)
- Abstract or textured backgrounds
- Artistic composition and unique perspective
- Confident, precise wording: "exactly", "identical", "specifically", "not altered"
"""
                                }

                                style_prompt = style_prompts.get(style_choice, style_prompts["E-commerce Product"])
                                description_response = gemini_model.generate_content([style_prompt, image_part])
                                image_description = description_response.text

                                if prompt.strip():
                                    final_prompt = f"{image_description}. Additionally, {prompt}"
                                else:
                                    final_prompt = image_description
                                
                                st.info(f"Enhanced Prompt ({style_choice}): {final_prompt}")

                        else:
                            if prompt.strip():
                                final_prompt = prompt
                                st.info(f"User Prompt: {final_prompt}")
                            else:
                                st.warning("Please either enter a prompt or upload a reference image to generate an image.")
                                st.stop()

                        # Generate image
                        with st.spinner("Generating your image... This may take a moment."):
                            generation_params = {
                                "prompt": final_prompt,
                                "number_of_images": num_images,
                                "add_watermark": False,
                            }
                            
                            if negative_prompt and negative_prompt.strip():
                                generation_params["negative_prompt"] = negative_prompt.strip()
                            
                            try:
                                response = imagen_model.generate_images(**generation_params)
                            except TypeError:
                                response = imagen_model.generate_images(**generation_params)
                        
                        if response and hasattr(response, 'images') and response.images:
                            images = response.images
                            primary_image = images[0]
                            st.session_state.generated_image = primary_image._pil_image
                            st.session_state.current_prompt = prompt
                            st.session_state.final_prompt = final_prompt
                            st.session_state.iteration_count = 1
                            st.session_state.negative_prompt = negative_prompt.strip() if negative_prompt else ""
                            st.session_state.current_style = style_choice
                            
                            count = len(images)
                            if count > 1:
                                st.success(f"✅ {count} images generated! Select your favorite below.")
                                cols = st.columns(min(4, count))
                                for idx, img_obj in enumerate(images):
                                    with cols[idx % len(cols)]:
                                        thumb = downscale_image_for_display(img_obj._pil_image, 320)
                                        st.image(thumb, caption=f"Option {idx+1}")
                                        if st.button(f"Use Option {idx+1}", key=f"use_option_{idx}"):
                                            st.session_state.generated_image = img_obj._pil_image
                                            st.success(f"✅ Selected Option {idx+1}")
                                            st.rerun()
                                
                                st.markdown("---")
                                st.markdown("### Current Selection")
                                st.image(downscale_image_for_display(st.session_state.generated_image, 640), 
                                        caption=f"Generated Image for: '{final_prompt}'")
                            else:
                                st.success(f"Image generated successfully! (Iteration #{st.session_state.iteration_count})")
                                disp_img = downscale_image_for_display(primary_image._pil_image, 640)
                                st.image(disp_img, caption=f"Generated Image for: '{final_prompt}'")
                            
                            # Add to Favorites button
                            col_fav1, col_fav2 = st.columns([1, 1])
                            with col_fav1:
                                if st.button("⭐ Add to Favorites", key="add_to_favorites_main"):
                                    img_byte_arr = BytesIO()
                                    st.session_state.generated_image.save(img_byte_arr, format='PNG')
                                    img_bytes = img_byte_arr.getvalue()
                                    
                                    favorite_entry = {
                                        'image': st.session_state.generated_image,
                                        'image_bytes': img_bytes,
                                        'prompt': final_prompt,
                                        'date': time.strftime("%Y-%m-%d %H:%M"),
                                        'iteration': st.session_state.iteration_count,
                                        'style': style_choice
                                    }
                                    
                                    is_duplicate = any(fav['prompt'] == final_prompt for fav in st.session_state.favorites)
                                    if not is_duplicate:
                                        st.session_state.favorites.append(favorite_entry)
                                        st.success("✨ Image added to favorites!")
                                        st.rerun()
                                    else:
                                        st.warning("⚠️ This image is already in your favorites!")
                            
                            with col_fav2:
                                st.markdown("💡 **Tip:** Add images to favorites to save them for later use!")
                        else:
                            st.error("No images were generated by the model. Try a different prompt.")

                    except Exception as e:
                        st.error(f"An error occurred during image generation: {str(e)}")
            
            # Feedback section
            if st.session_state.generated_image is not None:
                st.markdown('<div class="feedback-section">', unsafe_allow_html=True)
                st.markdown('<div class="feedback-header">🔄 Improve Your Image</div>', unsafe_allow_html=True)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown('<div class="image-display-card">', unsafe_allow_html=True)
                    disp_img = downscale_image_for_display(st.session_state.generated_image, 640)
                    st.image(disp_img, caption=f"Current Image (Iteration #{st.session_state.iteration_count})")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col2:
                    st.markdown('<div class="feedback-input-card">', unsafe_allow_html=True)
                    st.markdown('<div class="feedback-title">💡 Not satisfied with the result?</div>', unsafe_allow_html=True)
                    st.markdown('<div class="feedback-subtitle">Describe what you\'d like to change or improve:</div>', unsafe_allow_html=True)
                    
                    # Style choice for feedback regeneration
                    st.markdown('<div class="input-label">🎨 Style for Regeneration</div>', unsafe_allow_html=True)
                    feedback_style_choice = st.selectbox(
                        "Select style for regeneration:",
                        ["E-commerce Product", "Real-world Lifestyle", "Creative Artistic"],
                        key="feedback_style_choice",
                        index=["E-commerce Product", "Real-world Lifestyle", "Creative Artistic"].index(st.session_state.get('current_style', 'E-commerce Product')) if 'current_style' in st.session_state else 0,
                        label_visibility="collapsed"
                    )
                    
                    # Style descriptions for feedback
                    feedback_style_descriptions = {
                        "E-commerce Product": "Clean, professional photos with studio lighting, neutral backgrounds, and commercial appeal - perfect for product catalogs and online retail.",
                        "Real-world Lifestyle": "Natural, authentic images showing products in everyday use with natural lighting and relatable settings - ideal for lifestyle marketing.",
                        "Creative Artistic": "Dramatic, artistic photos with creative lighting, artistic backgrounds, and artistic composition - great for creative campaigns and social media."
                    }
                    
                    if feedback_style_choice in feedback_style_descriptions:
                        # Create style badge for feedback
                        feedback_style_class = {
                            "E-commerce Product": "ecommerce",
                            "Real-world Lifestyle": "lifestyle", 
                            "Creative Artistic": "creative"
                        }.get(feedback_style_choice, "ecommerce")
                        
                        st.markdown(f'<div class="style-badge {feedback_style_class}">🎨 {feedback_style_choice}</div>', unsafe_allow_html=True)
                        st.info(f"💡 **{feedback_style_choice}**: {feedback_style_descriptions[feedback_style_choice]}")
                    
                    feedback = st.text_area(
                        "Your feedback:",
                        height=120,
                        placeholder="e.g., Make it brighter, change the background to blue, add more detail...",
                        key="image_feedback",
                        label_visibility="collapsed"
                    )
                    
                    if st.button("🔄 Regenerate with Feedback", type="secondary", key="regenerate_button"):
                        if not feedback.strip():
                            st.warning("Please provide some feedback to improve the image.")
                        else:
                            try:
                                # Create enhanced prompt with feedback and style
                                style_enhancements = {
                                    "E-commerce Product": "Maintain clean, commercial photography style suitable for online retail with studio lighting and professional composition.",
                                    "Real-world Lifestyle": "Keep the natural, everyday setting with natural lighting and authentic atmosphere. For food, plants, or small objects: maintain macro lens perspective with precise focusing and detailed textures.",
                                    "Creative Artistic": "Maintain artistic, creative style with dramatic lighting and artistic composition."
                                }
                                
                                style_enhancement = style_enhancements.get(feedback_style_choice, "")
                                if style_enhancement:
                                    feedback_prompt = f"{st.session_state.final_prompt}. IMPROVEMENT NEEDED: {feedback.strip()}. STYLE: {style_enhancement}"
                                else:
                                    feedback_prompt = f"{st.session_state.final_prompt}. IMPROVEMENT NEEDED: {feedback.strip()}"
                                
                                with st.spinner("Regenerating image with your feedback..."):
                                    generation_params = {
                                        "prompt": feedback_prompt,
                                        "number_of_images": 1,
                                        "add_watermark": False,
                                    }
                                    
                                    if st.session_state.get('negative_prompt'):
                                        generation_params["negative_prompt"] = st.session_state.negative_prompt
                                    
                                    response = imagen_model.generate_images(**generation_params)
                                
                                if response and hasattr(response, 'images') and response.images:
                                    new_image = response.images[0]
                                    st.session_state.generated_image = new_image._pil_image
                                    st.session_state.final_prompt = feedback_prompt
                                    st.session_state.iteration_count += 1
                                    
                                    st.success(f"✨ Image regenerated successfully! (Iteration #{st.session_state.iteration_count})")
                                    st.rerun()
                                else:
                                    st.error("Failed to regenerate image. Please try again.")
                                    
                            except Exception as e:
                                st.error(f"Error during regeneration: {str(e)}")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                # Reset button
                if st.button("🗑️ Start Over", key="reset_button"):
                    for key in ['generated_image', 'current_prompt', 'final_prompt', 'negative_prompt', 'iteration_count']:
                        if key in st.session_state:
                            st.session_state[key] = None if key == 'generated_image' else "" if key != 'iteration_count' else 0
                    st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # --- VIDEO GENERATION TAB ---
        with tab2:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown('''
            <div class="section-header">
                <div class="icon">🎬</div>
                <div>Video Generation</div>
            </div>
            <div class="section-description">Create stunning videos from text descriptions or animate existing images</div>
            ''', unsafe_allow_html=True)
            
            # Source image selection
            source_choice = st.radio(
                "Source Image (optional):",
                ["No image (prompt only)", "Use generated image", "Upload image"],
                horizontal=True,
                key="video_source_choice",
            )

            uploaded_video_image = None
            image_bytes = None

            if source_choice == "Use generated image":
                if st.session_state.generated_image is None:
                    st.warning("No generated image found. Please upload an image or generate one first.")
                else:
                    st.image(st.session_state.generated_image, caption="Source Image", width=300)
                    img_byte_arr = BytesIO()
                    st.session_state.generated_image.save(img_byte_arr, format='PNG')
                    image_bytes = img_byte_arr.getvalue()
            elif source_choice == "Upload image":
                uploaded_video_image = st.file_uploader(
                    "Upload an image for the video",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="video_image_upload",
                )
                if uploaded_video_image is not None:
                    st.image(uploaded_video_image, caption="Source Image", width=300)
                    image_bytes = uploaded_video_image.getvalue()
            else:
                st.info("Using prompt only. No image will be provided to the video model.")

            # Video prompt
            st.markdown('<div class="input-group">', unsafe_allow_html=True)
            st.markdown('<div class="input-label">🎬 Video Prompt</div>', unsafe_allow_html=True)
            st.markdown('<div class="input-description">Describe the video motion and style you want to create</div>', unsafe_allow_html=True)
            
            video_prompt = st.text_area(
                "Enter your video prompt:",
                height=200,
                placeholder="A smooth camera rotation around the product, highlighting its features with cinematic lighting...",
                key="video_prompt_input",
                label_visibility="collapsed"
            )
            st.markdown('</div>', unsafe_allow_html=True)
            
            if st.button("🎬 Generate Video", type="primary", key="generate_video_button"):
                if not video_prompt.strip():
                    st.warning("Please enter a video prompt describing the motion or action.")
                else:
                    try:
                        with st.spinner("Generating video... This may take several minutes."):
                            video_result = generate_video_from_image(image_bytes, video_prompt)

                            if isinstance(video_result, str):
                                try:
                                    video_result = base64.b64decode(video_result)
                                except Exception:
                                    pass

                            if isinstance(video_result, bytes) and video_result.startswith(b'AAAA'):
                                try:
                                    video_result = base64.b64decode(video_result)
                                except Exception:
                                    pass

                            if isinstance(video_result, (bytes, bytearray)) and len(video_result) > 0:
                                st.session_state.generated_video = video_result
                                st.session_state.video_iteration_count = 1
                                
                                st.success("Video generated successfully!")
                                
                                try:
                                    video_b64 = base64.b64encode(video_result).decode('utf-8')
                                    video_html = f"""
                                    <div style="margin: 20px 0;">
                                        <video width="100%" height="auto" controls preload="metadata" style="border: 2px solid var(--primary-color); border-radius: var(--radius-lg);">
                                            <source src="data:video/mp4;base64,{video_b64}" type="video/mp4">
                                            Your browser does not support the video tag.
                                        </video>
                                        <p style="font-size: 12px; color: var(--text-secondary); margin-top: 5px;">
                                            Video size: {len(video_result)} bytes | Format: MP4
                                        </p>
                                    </div>
                                    """
                                    st.markdown(video_html, unsafe_allow_html=True)
                                except Exception as e1:
                                    st.warning(f"Video display failed: {e1}")
                                
                                st.download_button(
                                    label="💾 Download Video",
                                    data=video_result,
                                    file_name="generated_video.mp4",
                                    mime="video/mp4",
                                    key="download_generated_video"
                                )
                                
                            else:
                                st.error("Video generation did not return video bytes.")
                    except Exception as e:
                        st.error(f"An error occurred during video generation: {str(e)}")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- FAVORITES TAB ---
        with tab3:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown('''
            <div class="section-header">
                <div class="icon">⭐</div>
                <div>Your Favorite Images</div>
            </div>
            <div class="section-description">Manage and download your favorite generated images</div>
            ''', unsafe_allow_html=True)
            
            if st.session_state.favorites:
                st.markdown(f"**Saved Images ({len(st.session_state.favorites)})**")
                
                # Display favorites
                for i, favorite in enumerate(st.session_state.favorites):
                    st.markdown('<div class="favorite-item">', unsafe_allow_html=True)
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.image(favorite['image'], caption=f"Favorite #{i+1}", width=400)
                    
                    with col2:
                        st.markdown(f"**Prompt:** {favorite['prompt'][:150]}...")
                        
                        favorite_style = favorite.get('style', 'E-commerce Product')
                        favorite_style_class = {
                            "E-commerce Product": "ecommerce",
                            "Real-world Lifestyle": "lifestyle", 
                            "Creative Artistic": "creative"
                        }.get(favorite_style, "ecommerce")
                        
                        st.markdown(f'<div class="style-badge {favorite_style_class}">🎨 {favorite_style}</div>', unsafe_allow_html=True)
                        
                        st.markdown(f"**Date:** {favorite['date']}")
                        st.markdown(f"**Iteration:** #{favorite['iteration']}")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button(f"🗑️ Remove", key=f"remove_fav_{i}"):
                                st.session_state.favorites.pop(i)
                                st.rerun()
                        
                        with col_btn2:
                            img_bytes = favorite['image_bytes']
                            st.download_button(
                                label="💾 Download",
                                data=img_bytes,
                                file_name=f"favorite_image_{i+1}.png",
                                mime="image/png",
                                key=f"download_fav_{i}"
                            )
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                if st.button("🗑️ Clear All Favorites", key="clear_all_favorites"):
                    st.session_state.favorites = []
                    st.rerun()
                    
            else:
                st.markdown('''
                <div class="no-content-message">
                    <div class="no-content-icon">⭐</div>
                    <div class="no-content-title">No Favorites Yet</div>
                    <div class="no-content-description">Generate some images first, then add them to your favorites to see them here!</div>
                </div>
                ''', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
        # --- GEMINI IMAGE GENERATION TAB ---
        with tab4:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown('''
            <div class="section-header">
                <div class="icon">🧪</div>
                <div>Experimental Gemini Image Generation</div>
            </div>
            <div class="section-description">Transform existing images using Gemini's experimental image generation capabilities</div>
            ''', unsafe_allow_html=True)

            col_g_left, col_g_right = st.columns([1, 2])

            with col_g_left:
                st.markdown('<div class="input-group">', unsafe_allow_html=True)
                st.markdown('<div class="input-label">📁 Input Image</div>', unsafe_allow_html=True)
                gemini_input_image = st.file_uploader(
                    "Choose an image file:",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="gemini_image_upload",
                    label_visibility="collapsed"
                )
                if gemini_input_image is not None:
                    st.image(gemini_input_image, caption="Input Image", width=300)
                st.markdown('</div>', unsafe_allow_html=True)

            with col_g_right:
                st.markdown('<div class="input-group">', unsafe_allow_html=True)
                st.markdown('<div class="input-label">✍️ Text Instruction</div>', unsafe_allow_html=True)
                st.markdown('<div class="input-description">Instructions for transforming the image</div>', unsafe_allow_html=True)
                gemini_text_prompt = st.text_area(
                    "Enter instruction for image generation:",
                    height=200,
                    placeholder="please color this beautifully using red, green, blue",
                    key="gemini_text_prompt",
                    label_visibility="collapsed"
                )
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Style Choice Section for Gemini
                st.markdown('<div class="input-group">', unsafe_allow_html=True)
                st.markdown('<div class="input-label">🎨 Generation Style</div>', unsafe_allow_html=True)
                st.markdown('<div class="input-description">Choose the style for the image transformation</div>', unsafe_allow_html=True)
                gemini_style_choice = st.selectbox(
                    "Select image style:",
                    ["E-commerce Product", "Real-world Lifestyle", "Creative Artistic"],
                    key="gemini_style_choice",
                    label_visibility="collapsed"
                )
                
                # Style descriptions (reuse from Tab 1)
                gemini_style_descriptions = {
                    "E-commerce Product": "Clean, professional photos with studio lighting, neutral backgrounds, and commercial appeal - perfect for product catalogs and online retail.",
                    "Real-world Lifestyle": "Natural, authentic images showing products in everyday use with natural lighting and relatable settings - ideal for lifestyle marketing.",
                    "Creative Artistic": "Dramatic, artistic photos with creative lighting, artistic backgrounds, and artistic composition - great for creative campaigns and social media."
                }
                
                if gemini_style_choice in gemini_style_descriptions:
                    # Create style badge for Gemini
                    gemini_style_class = {
                        "E-commerce Product": "ecommerce",
                        "Real-world Lifestyle": "lifestyle", 
                        "Creative Artistic": "creative"
                    }.get(gemini_style_choice, "ecommerce")
                    
                    st.markdown(f'<div class="style-badge {gemini_style_class}">🎨 {gemini_style_choice}</div>', unsafe_allow_html=True)
                    st.info(f"💡 **{gemini_style_choice}**: {gemini_style_descriptions[gemini_style_choice]}")
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Negative Prompt (optional)
                st.markdown('<div class="input-group">', unsafe_allow_html=True)
                st.markdown('<div class="input-label">🚫 Negative Prompt</div>', unsafe_allow_html=True)
                st.markdown('<div class="input-description">Specify what you DON\'T want in the image</div>', unsafe_allow_html=True)
                gemini_negative_prompt = st.text_area(
                    "Negative prompt:",
                    height=60,
                    placeholder="blurry, distorted, low quality, text overlay, watermarks, multiple objects, cluttered background...",
                    key="gemini_negative_prompt",
                    label_visibility="collapsed"
                )
                st.markdown('</div>', unsafe_allow_html=True)
                
                gemini_generate_clicked = st.button("🧪 Generate with Gemini", type="primary", key="gemini_generate_btn")

            if gemini_generate_clicked:
                if gemini_input_image is None:
                    st.warning("Please upload an image to transform.")
                else:
                    try:
                        # Prepare contents for the Gemini image generation model
                        if client is None:
                            if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") != SERVICE_ACCOUNT_PATH:
                                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SERVICE_ACCOUNT_PATH
                            if os.environ.get("GOOGLE_CLOUD_PROJECT") != PROJECT_ID:
                                os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
                            client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

                        image_bytes = gemini_input_image.getvalue()
                        mime_type = gemini_input_image.type

                        # Use only the experimental Gemini image-capable model
                        model_candidates = ["gemini-2.0-flash-preview-image-generation"]

                        # Style-specific system prompts for Gemini image generation
                        gemini_style_prompts = {
                            "E-commerce Product": """Transform this image following e-commerce product photography standards. Create a clean, professional product image with: studio lighting (soft key light with subtle rim lighting), neutral or white background, sharp focus on product details, minimal clutter, commercial composition suitable for online retail catalogs. Maintain all original product details exactly while enhancing the professional presentation. Focus on clean, commercial photography suitable for product sales.""",
                            
                            "Real-world Lifestyle": """Transform this image to show the product in a natural, everyday lifestyle setting. Create an authentic environment that demonstrates how people would actually use this product in real life. Use natural lighting (soft window light or realistic indoor/outdoor lighting), realistic props and furniture, warm and inviting atmosphere. Show the product integrated naturally into daily life scenarios like homes, offices, or outdoor settings. Keep it authentic and relatable.""",
                            
                            "Creative Artistic": """Transform this image with artistic and creative vision. Apply dramatic lighting effects, creative composition, artistic backgrounds, and bold visual elements. Use creative techniques like dramatic shadows, colored lighting, artistic angles, and creative visual effects. Make the product the focal point while creating an artistic, memorable image that stands out. Emphasize creativity, drama, and artistic appeal."""
                        }
                        
                        # Get the style-specific system prompt
                        style_system_prompt = gemini_style_prompts.get(gemini_style_choice, gemini_style_prompts["E-commerce Product"])
                        
                        # Build final text instruction with style guidance, user prompt, and negative prompt
                        _text_instruction = f"{style_system_prompt}\n\n"
                        
                        if gemini_text_prompt.strip():
                            _text_instruction += f"Additional specific instructions: {gemini_text_prompt.strip()}\n\n"
                        
                        if gemini_negative_prompt and gemini_negative_prompt.strip():
                            _text_instruction += f"Avoid these elements: {gemini_negative_prompt.strip()}\n\n"
                            
                        _text_instruction += "Please prioritize high visual fidelity, clean edges, accurate colors, high resolution, minimal artifacts, and photo-realistic rendering while following the specified style requirements."
                        
                        # Show the enhanced prompt to user
                        st.info(f"🎨 **Style-Enhanced Prompt ({gemini_style_choice})**: {_text_instruction}")

                        contents = [
                            types.Content(
                                role="user",
                                parts=[
                                    types.Part(
                                        inline_data=types.Blob(
                                            mime_type=mime_type,
                                            data=image_bytes,
                                        )
                                    ),
                                    types.Part.from_text(text=_text_instruction),
                                ],
                            )
                        ]
                        
                        generate_content_config = types.GenerateContentConfig(
                            temperature=0.3,
                            top_p=0.95,
                            top_k=40,
                            max_output_tokens=8192,
                            response_modalities=["image", "text"],
                            safety_settings=[
                                types.SafetySetting(
                                    category="HARM_CATEGORY_CIVIC_INTEGRITY",
                                    threshold="OFF",
                                ),
                            ],
                        )

                        output_image_bytes = None
                        output_image_mime = None
                        text_chunks = []

                        with st.spinner("Generating image with Gemini..."):
                            resp = None
                            selected_model = None
                            last_err = None
                            for _model_name in model_candidates:
                                try:
                                    resp = client.models.generate_content(
                                        model=_model_name,
                                        contents=contents,
                                        config=generate_content_config,
                                    )
                                    selected_model = _model_name
                                    break
                                except Exception as _e:
                                    # Try the next candidate if model not found in this region/project
                                    if "NOT_FOUND" in str(_e) or "not found" in str(_e).lower():
                                        last_err = _e
                                        continue
                                    raise
                            if resp is None:
                                raise last_err or Exception("No suitable Gemini image-capable model found in this region.")

                        try:
                            if resp and getattr(resp, "candidates", None):
                                for candidate in resp.candidates:
                                    content = getattr(candidate, "content", None)
                                    if not content:
                                        continue
                                    for part in getattr(content, "parts", []):
                                        if hasattr(part, "inline_data") and part.inline_data and getattr(part.inline_data, "data", None):
                                            output_image_bytes = part.inline_data.data
                                            output_image_mime = getattr(part.inline_data, "mime_type", None)
                                        if hasattr(part, "text") and part.text:
                                            text_chunks.append(part.text)
                        except Exception:
                            pass

                        if output_image_bytes:
                            import io as _io
                            import base64 as _b64
                            display_bytes = output_image_bytes
                            valid_image = False
                            try:
                                from PIL import Image as _PILImage
                                _PILImage.open(_io.BytesIO(display_bytes)).verify()
                                valid_image = True
                            except Exception:
                                try:
                                    decoded = _b64.b64decode(display_bytes)
                                    from PIL import Image as _PILImage
                                    _PILImage.open(_io.BytesIO(decoded)).verify()
                                    display_bytes = decoded
                                    valid_image = True
                                except Exception:
                                    valid_image = False

                            if valid_image:
                                st.success("✅ Image generated successfully!")
                                # Store generated image in session state for feedback functionality
                                from PIL import Image as _PILImage
                                st.session_state.gemini_generated_image = _PILImage.open(_io.BytesIO(display_bytes))
                                st.session_state.gemini_image_bytes = display_bytes
                                st.session_state.gemini_iteration_count = st.session_state.get('gemini_iteration_count', 0) + 1
                                st.session_state.gemini_current_style = gemini_style_choice
                                st.session_state.gemini_original_prompt = _text_instruction
                                
                                st.image(_io.BytesIO(display_bytes), caption="Gemini Generated Image", use_container_width=True)
                                st.download_button(
                                    label="💾 Download Image",
                                    data=display_bytes,
                                    file_name="gemini_output.jpg" if (output_image_mime or "").endswith("jpeg") or (output_image_mime or "").endswith("jpg") else "gemini_output.png",
                                    mime=output_image_mime or "image/jpeg",
                                    key="download_gemini_image",
                                )
                                
                                # Add to Favorites button for main generation
                                if st.button("⭐ Add to Favorites", key="add_to_favorites_gemini_main"):
                                    if 'favorites' not in st.session_state:
                                        st.session_state.favorites = []
                                    
                                    # Convert PIL image to bytes for storage
                                    img_byte_arr = BytesIO()
                                    st.session_state.gemini_generated_image.save(img_byte_arr, format='PNG')
                                    img_bytes = img_byte_arr.getvalue()
                                    
                                    st.session_state.favorites.append({
                                        'image': st.session_state.gemini_generated_image.copy(),
                                        'image_bytes': img_bytes,
                                        'prompt': f"Gemini: {gemini_text_prompt if gemini_text_prompt else 'Image transformation'}",
                                        'style': gemini_style_choice,
                                        'date': time.strftime("%Y-%m-%d %H:%M"),
                                        'iteration': st.session_state.gemini_iteration_count
                                    })
                                    st.success("Added to favorites! ⭐")
                                    st.rerun()
                                
                                if text_chunks:
                                    st.info("\n".join(text_chunks[-3:]))
                            else:
                                st.warning("Received bytes could not be decoded as an image. Showing text response if available.")
                                if text_chunks:
                                    st.code("\n".join(text_chunks), language="markdown")
                                else:
                                    st.error("Gemini did not return a decodable image or text. Try adjusting your prompt.")
                        else:
                            if text_chunks:
                                st.warning("No image bytes found in the stream. Showing text response:")
                                st.code("\n".join(text_chunks), language="markdown")
                            else:
                                st.error("Gemini did not return an image or text. Try adjusting your prompt.")
                    except Exception as e:
                        st.error(f"Gemini image generation failed: {e}")
            
            # --- Gemini Feedback Section ---
            if st.session_state.get('gemini_generated_image') is not None:
                st.markdown('<div class="feedback-section">', unsafe_allow_html=True)
                st.markdown('<div class="feedback-header">🔄 Improve Your Gemini Image</div>', unsafe_allow_html=True)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown('<div class="image-display-card">', unsafe_allow_html=True)
                    disp_img = downscale_image_for_display(st.session_state.gemini_generated_image, 640)
                    st.image(disp_img, caption=f"Current Gemini Image (Iteration #{st.session_state.get('gemini_iteration_count', 1)})")
                    
                    # Add to Favorites button for feedback section
                    col_fav_fb1, col_fav_fb2 = st.columns([1, 1])
                    with col_fav_fb1:
                        if st.button("⭐ Add to Favorites", key="add_to_favorites_gemini_feedback"):
                            if 'favorites' not in st.session_state:
                                st.session_state.favorites = []
                            
                            # Convert PIL image to bytes for storage
                            img_byte_arr = BytesIO()
                            st.session_state.gemini_generated_image.save(img_byte_arr, format='PNG')
                            img_bytes = img_byte_arr.getvalue()
                            
                            st.session_state.favorites.append({
                                'image': st.session_state.gemini_generated_image.copy(),
                                'image_bytes': img_bytes,
                                'prompt': f"Gemini Feedback: Iteration #{st.session_state.get('gemini_iteration_count', 1)}",
                                'style': st.session_state.get('gemini_current_style', 'E-commerce Product'),
                                'date': time.strftime("%Y-%m-%d %H:%M"),
                                'iteration': st.session_state.get('gemini_iteration_count', 1)
                            })
                            st.success("Added to favorites! ⭐")
                            st.rerun()
                    
                    with col_fav_fb2:
                        # Download button for feedback section
                        if st.session_state.get('gemini_image_bytes'):
                            st.download_button(
                                label="💾 Download",
                                data=st.session_state.gemini_image_bytes,
                                file_name=f"gemini_feedback_iteration_{st.session_state.get('gemini_iteration_count', 1)}.jpg",
                                mime="image/jpeg",
                                key="download_gemini_feedback"
                            )
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col2:
                    st.markdown('<div class="feedback-input-card">', unsafe_allow_html=True)
                    st.markdown('<div class="feedback-title">💡 Not satisfied with the result?</div>', unsafe_allow_html=True)
                    st.markdown('<div class="feedback-subtitle">Describe what you\'d like to change or improve:</div>', unsafe_allow_html=True)
                    
                    # Style choice for feedback regeneration
                    st.markdown('<div class="input-label">🎨 Style for Regeneration</div>', unsafe_allow_html=True)
                    gemini_feedback_style_choice = st.selectbox(
                        "Select style for regeneration:",
                        ["E-commerce Product", "Real-world Lifestyle", "Creative Artistic"],
                        key="gemini_feedback_style_choice",
                        index=["E-commerce Product", "Real-world Lifestyle", "Creative Artistic"].index(st.session_state.get('gemini_current_style', 'E-commerce Product')) if 'gemini_current_style' in st.session_state else 0,
                        label_visibility="collapsed"
                    )
                    
                    # Style descriptions for feedback
                    gemini_feedback_style_descriptions = {
                        "E-commerce Product": "Clean, professional photos with studio lighting, neutral backgrounds, and commercial appeal - perfect for product catalogs and online retail.",
                        "Real-world Lifestyle": "Natural, authentic images showing products in everyday use with natural lighting and relatable settings - ideal for lifestyle marketing.",
                        "Creative Artistic": "Dramatic, artistic photos with creative lighting, artistic backgrounds, and artistic composition - great for creative campaigns and social media."
                    }
                    
                    if gemini_feedback_style_choice in gemini_feedback_style_descriptions:
                        # Create style badge for feedback
                        gemini_feedback_style_class = {
                            "E-commerce Product": "ecommerce",
                            "Real-world Lifestyle": "lifestyle", 
                            "Creative Artistic": "creative"
                        }.get(gemini_feedback_style_choice, "ecommerce")
                        
                        st.markdown(f'<div class="style-badge {gemini_feedback_style_class}">🎨 {gemini_feedback_style_choice}</div>', unsafe_allow_html=True)
                        st.info(f"💡 **{gemini_feedback_style_choice}**: {gemini_feedback_style_descriptions[gemini_feedback_style_choice]}")
                    
                    gemini_feedback = st.text_area(
                        "Your feedback:",
                        height=120,
                        placeholder="e.g., Make it brighter, change the background to blue, add more detail, use different lighting...",
                        key="gemini_feedback",
                        label_visibility="collapsed"
                    )
                
                    if st.button("🔄 Regenerate with Feedback", type="secondary", key="regenerate_gemini_button"):
                        if not gemini_feedback.strip():
                            st.warning("Please provide some feedback to improve the image.")
                        else:
                            st.info("🧪 Gemini feedback regeneration requires the original input image to be available.")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Start Over button for Gemini
                if st.button("🗑️ Start Over (Gemini)", key="reset_gemini_button"):
                    for key in ['gemini_generated_image', 'gemini_image_bytes', 'gemini_iteration_count', 'gemini_current_style', 'gemini_original_prompt']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        st.error("Application cannot start due to authentication failure.")

    # Footer
    st.markdown("---")
    st.markdown("Powered by [Google Vertex AI](https://cloud.google.com/vertex-ai) and [Streamlit](https://streamlit.io).")

if __name__ == "__main__":
    main() 