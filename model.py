"""
AgriSetu Model Training Pipeline
Trains and saves ML models for crop prediction system

Usage:
    python train_models.py
    python train_models.py --data_path "your_dataset.xlsx"
"""

import os
import sys
import argparse
import warnings
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    mean_absolute_error, mean_squared_error, r2_score,
    classification_report, confusion_matrix
)

# Suppress warnings
warnings.filterwarnings('ignore')

# ================== CONFIGURATION ==================
class Config:
    """Training configuration"""
    
    # Paths
    MODELS_DIR = Path("models")
    DATASET_PATH = Path("smart_agriculture_ml_dataset.xlsx")
    
    # Feature columns
    FEATURE_COLUMNS = [
        "Soil_Moisture_%",
        "Soil_Temperature_C",
        "Rainfall_ml",
        "Air_Temperature_C",
        "Humidity_%"
    ]
    
    # Target columns
    CROP_COLUMN = "Recommended_Crop"
    MONTHS_COLUMN = "Growth_Duration_Months"
    
    # Model parameters
    RANDOM_STATE = 42
    TEST_SIZE = 0.2
    
    # Crop model hyperparameters
    CROP_MODEL_PARAMS = {
        'n_estimators': 150,
        'max_depth': 15,
        'min_samples_split': 5,
        'min_samples_leaf': 2,
        'random_state': RANDOM_STATE,
        'n_jobs': -1
    }
    
    # Month model hyperparameters
    MONTH_MODEL_PARAMS = {
        'n_estimators': 100,
        'max_depth': 10,
        'min_samples_split': 4,
        'min_samples_leaf': 1,
        'random_state': RANDOM_STATE,
        'n_jobs': -1
    }
    
    # Output files
    CROP_MODEL_FILE = MODELS_DIR / "crop_model.pkl"
    MONTH_MODEL_FILE = MODELS_DIR / "month_model.pkl"
    LABEL_ENCODER_FILE = MODELS_DIR / "label_encoder.pkl"
    CROP_MONTH_LOOKUP_FILE = MODELS_DIR / "crop_month_lookup.pkl"
    SCALER_FILE = MODELS_DIR / "scaler.pkl"
    METADATA_FILE = MODELS_DIR / "model_metadata.pkl"
    
    @classmethod
    def create_directories(cls):
        """Create necessary directories"""
        cls.MODELS_DIR.mkdir(exist_ok=True, parents=True)


# ================== DATA LOADING ==================
def load_dataset(file_path: Path) -> pd.DataFrame:
    """
    Load dataset from Excel or CSV file
    
    Args:
        file_path: Path to dataset file
        
    Returns:
        DataFrame with agricultural data
    """
    print(f"\n📂 Loading dataset from: {file_path}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset not found: {file_path}")
    
    # Load based on extension
    if file_path.suffix in ['.xlsx', '.xls']:
        df = pd.read_excel(file_path)
    elif file_path.suffix == '.csv':
        df = pd.read_csv(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")
    
    print(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")
    
    return df


def validate_dataset(df: pd.DataFrame) -> bool:
    """
    Validate dataset has required columns
    
    Args:
        df: DataFrame to validate
        
    Returns:
        True if valid, raises error otherwise
    """
    required_columns = Config.FEATURE_COLUMNS + [Config.CROP_COLUMN, Config.MONTHS_COLUMN]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    
    print("✅ Dataset validation passed")
    return True


def explore_dataset(df: pd.DataFrame):
    """
    Print dataset statistics and information
    
    Args:
        df: DataFrame to explore
    """
    print("\n" + "="*60)
    print("📊 DATASET EXPLORATION")
    print("="*60)
    
    # Basic info
    print(f"\n📈 Dataset Shape: {df.shape}")
    
    # Feature statistics
    print("\n📊 Feature Statistics:")
    print(df[Config.FEATURE_COLUMNS].describe().round(2))
    
    # Target distribution
    print(f"\n🌾 Crop Distribution:")
    crop_counts = df[Config.CROP_COLUMN].value_counts()
    for crop, count in crop_counts.items():
        print(f"   {crop}: {count} ({count/len(df)*100:.1f}%)")
    
    print(f"\n⏱️ Growth Duration Statistics:")
    print(df[Config.MONTHS_COLUMN].describe().round(2))
    
    # Missing values
    print(f"\n🔍 Missing Values:")
    missing = df.isnull().sum()
    if missing.sum() > 0:
        print(missing[missing > 0])
    else:
        print("   No missing values")
    
    print("="*60)


# ================== DATA PREPROCESSING ==================
def preprocess_data(df: pd.DataFrame) -> tuple:
    """
    Preprocess data for model training
    
    Args:
        df: Raw DataFrame
        
    Returns:
        Tuple of (X, y_crop, y_months, label_encoder, scaler)
    """
    print("\n🔧 Preprocessing data...")
    
    # Extract features
    X = df[Config.FEATURE_COLUMNS].copy()
    
    # Extract targets
    y_crop_raw = df[Config.CROP_COLUMN].copy()
    y_months = df[Config.MONTHS_COLUMN].copy()
    
    # Encode crop labels
    label_encoder = LabelEncoder()
    y_crop = label_encoder.fit_transform(y_crop_raw)
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_scaled = pd.DataFrame(X_scaled, columns=Config.FEATURE_COLUMNS)
    
    print(f"✅ Encoded {len(label_encoder.classes_)} crop classes")
    print(f"   Classes: {', '.join(label_encoder.classes_)}")
    
    return X_scaled, y_crop, y_months, label_encoder, scaler


# ================== MODEL TRAINING ==================
def train_crop_model(X_train, y_train, X_test, y_test, label_encoder):
    """
    Train Random Forest classifier for crop prediction
    
    Args:
        X_train, y_train: Training data
        X_test, y_test: Testing data
        label_encoder: Fitted label encoder
        
    Returns:
        Trained model and metrics
    """
    print("\n🌾 Training Crop Prediction Model...")
    print("-" * 40)
    
    # Create and train model
    model = RandomForestClassifier(**Config.CROP_MODEL_PARAMS)
    model.fit(X_train, y_train)
    
    # Predictions
    y_pred = model.predict(X_test)
    
    # Metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average='weighted')
    recall = recall_score(y_test, y_pred, average='weighted')
    f1 = f1_score(y_test, y_pred, average='weighted')
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=5)
    
    print(f"✅ Accuracy: {accuracy*100:.2f}%")
    print(f"   Precision: {precision*100:.2f}%")
    print(f"   Recall: {recall*100:.2f}%")
    print(f"   F1-Score: {f1*100:.2f}%")
    print(f"   CV Score (5-fold): {cv_scores.mean()*100:.2f}% (+/- {cv_scores.std()*100:.2f}%)")
    
    # Feature importance
    print("\n📊 Feature Importance:")
    importances = model.feature_importances_
    for name, importance in zip(Config.FEATURE_COLUMNS, importances):
        print(f"   {name}: {importance*100:.2f}%")
    
    # Classification report
    print("\n📋 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=label_encoder.classes_))
    
    metrics = {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'cv_mean': cv_scores.mean(),
        'cv_std': cv_scores.std(),
        'feature_importance': dict(zip(Config.FEATURE_COLUMNS, importances))
    }
    
    return model, metrics


def train_month_model(X_train, y_train, X_test, y_test):
    """
    Train Random Forest regressor for growth duration prediction
    
    Args:
        X_train, y_train: Training data
        X_test, y_test: Testing data
        
    Returns:
        Trained model and metrics
    """
    print("\n⏱️ Training Growth Duration Model...")
    print("-" * 40)
    
    # Create and train model
    model = RandomForestRegressor(**Config.MONTH_MODEL_PARAMS)
    model.fit(X_train, y_train)
    
    # Predictions
    y_pred = model.predict(X_test)
    
    # Metrics
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_test, y_pred)
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='neg_mean_absolute_error')
    
    print(f"✅ MAE: {mae:.2f} months")
    print(f"   RMSE: {rmse:.2f} months")
    print(f"   R² Score: {r2:.3f}")
    print(f"   CV MAE (5-fold): {-cv_scores.mean():.2f} months (+/- {cv_scores.std():.2f})")
    
    # Feature importance
    print("\n📊 Feature Importance:")
    importances = model.feature_importances_
    for name, importance in zip(Config.FEATURE_COLUMNS, importances):
        print(f"   {name}: {importance*100:.2f}%")
    
    metrics = {
        'mae': mae,
        'rmse': rmse,
        'r2': r2,
        'cv_mae_mean': -cv_scores.mean(),
        'cv_mae_std': cv_scores.std(),
        'feature_importance': dict(zip(Config.FEATURE_COLUMNS, importances))
    }
    
    return model, metrics


def create_crop_month_lookup(df: pd.DataFrame) -> dict:
    """
    Create lookup table for crop to average growth months
    
    Args:
        df: Original DataFrame with crop and months columns
        
    Returns:
        Dictionary mapping crop names to average growth months
    """
    print("\n📚 Creating crop-month lookup table...")
    
    lookup = df.groupby(Config.CROP_COLUMN)[Config.MONTHS_COLUMN].mean().round().astype(int).to_dict()
    
    print(f"✅ Created lookup for {len(lookup)} crops")
    
    return lookup


# ================== MODEL SAVING ==================
def save_models(crop_model, month_model, label_encoder, scaler, 
                crop_month_lookup, metrics):
    """
    Save all trained models and artifacts
    
    Args:
        crop_model: Trained crop classifier
        month_model: Trained month regressor
        label_encoder: Fitted label encoder
        scaler: Fitted standard scaler
        crop_month_lookup: Crop to months lookup dictionary
        metrics: Dictionary of model metrics
    """
    print("\n💾 Saving models...")
    print("-" * 40)
    
    # Create models directory
    Config.MODELS_DIR.mkdir(exist_ok=True)
    
    # Save individual models
    joblib.dump(crop_model, Config.CROP_MODEL_FILE)
    print(f"✅ Saved: {Config.CROP_MODEL_FILE}")
    
    joblib.dump(month_model, Config.MONTH_MODEL_FILE)
    print(f"✅ Saved: {Config.MONTH_MODEL_FILE}")
    
    joblib.dump(label_encoder, Config.LABEL_ENCODER_FILE)
    print(f"✅ Saved: {Config.LABEL_ENCODER_FILE}")
    
    joblib.dump(scaler, Config.SCALER_FILE)
    print(f"✅ Saved: {Config.SCALER_FILE}")
    
    joblib.dump(crop_month_lookup, Config.CROP_MONTH_LOOKUP_FILE)
    print(f"✅ Saved: {Config.CROP_MONTH_LOOKUP_FILE}")
    
    # Save metadata
    metadata = {
        'training_date': datetime.now().isoformat(),
        'feature_columns': Config.FEATURE_COLUMNS,
        'crop_classes': label_encoder.classes_.tolist(),
        'crop_model_params': Config.CROP_MODEL_PARAMS,
        'month_model_params': Config.MONTH_MODEL_PARAMS,
        'metrics': metrics,
        'python_version': sys.version,
        'library_versions': {
            'pandas': pd.__version__,
            'numpy': np.__version__,
            'sklearn': joblib.load.__module__
        }
    }
    
    joblib.dump(metadata, Config.METADATA_FILE)
    print(f"✅ Saved: {Config.METADATA_FILE}")
    
    # Print file sizes
    print("\n📦 Model File Sizes:")
    for file in Config.MODELS_DIR.glob("*.pkl"):
        size_kb = file.stat().st_size / 1024
        print(f"   {file.name}: {size_kb:.1f} KB")


# ================== MODEL TESTING ==================
def test_saved_models():
    """
    Test that saved models can be loaded and used
    
    Returns:
        True if all tests pass
    """
    print("\n🧪 Testing saved models...")
    print("-" * 40)
    
    try:
        # Load models
        crop_model = joblib.load(Config.CROP_MODEL_FILE)
        month_model = joblib.load(Config.MONTH_MODEL_FILE)
        label_encoder = joblib.load(Config.LABEL_ENCODER_FILE)
        scaler = joblib.load(Config.SCALER_FILE)
        lookup = joblib.load(Config.CROP_MONTH_LOOKUP_FILE)
        
        print("✅ All models loaded successfully")
        
        # Test prediction with sample data
        sample_input = pd.DataFrame([{
            "Soil_Moisture_%": 55.0,
            "Soil_Temperature_C": 28.0,
            "Rainfall_ml": 120.0,
            "Air_Temperature_C": 30.0,
            "Humidity_%": 65.0
        }])
        
        # Scale input
        sample_scaled = scaler.transform(sample_input)
        
        # Predict
        crop_pred = crop_model.predict(sample_scaled)
        month_pred = month_model.predict(sample_scaled)
        
        crop_name = label_encoder.inverse_transform(crop_pred)[0]
        months = round(month_pred[0])
        
        print(f"\n📊 Sample Prediction Test:")
        print(f"   Input: Moisture=55%, Temp=28°C, Rainfall=120ml")
        print(f"   Predicted Crop: {crop_name}")
        print(f"   Predicted Months: {months}")
        print(f"   Lookup Months for {crop_name}: {lookup.get(crop_name, 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Model testing failed: {e}")
        return False


# ================== PREDICTION DEMO ==================
def demo_prediction():
    """
    Demonstrate prediction with loaded models and generate sample PDF report
    """
    print("\n🎯 DEMO: Generating Sample Prediction Report")
    print("-" * 40)
    
    try:
        # Load models
        crop_model = joblib.load(Config.CROP_MODEL_FILE)
        month_model = joblib.load(Config.MONTH_MODEL_FILE)
        label_encoder = joblib.load(Config.LABEL_ENCODER_FILE)
        scaler = joblib.load(Config.SCALER_FILE)
        
        # Sample sensor data (simulating real readings)
        sample_inputs = [
            {"Soil_Moisture_%": 45.0, "Soil_Temperature_C": 22.0, 
             "Rainfall_ml": 90.0, "Air_Temperature_C": 25.0, "Humidity_%": 60.0},
            {"Soil_Moisture_%": 75.0, "Soil_Temperature_C": 30.0, 
             "Rainfall_ml": 150.0, "Air_Temperature_C": 32.0, "Humidity_%": 80.0},
            {"Soil_Moisture_%": 30.0, "Soil_Temperature_C": 18.0, 
             "Rainfall_ml": 50.0, "Air_Temperature_C": 20.0, "Humidity_%": 40.0},
        ]
        
        print("\n📊 Multiple Scenario Predictions:\n")
        print(f"{'Moisture':<10} {'Temp':<8} {'Rainfall':<10} {'Crop':<15} {'Months':<8}")
        print("-" * 55)
        
        for sample in sample_inputs:
            df = pd.DataFrame([sample])
            scaled = scaler.transform(df)
            
            crop_pred = crop_model.predict(scaled)
            month_pred = month_model.predict(scaled)
            
            crop = label_encoder.inverse_transform(crop_pred)[0]
            months = round(month_pred[0])
            
            print(f"{sample['Soil_Moisture_%']:<10.1f} "
                  f"{sample['Soil_Temperature_C']:<8.1f} "
                  f"{sample['Rainfall_ml']:<10.1f} "
                  f"{crop:<15} "
                  f"{months:<8}")
        
        # Generate simple PDF report for the first sample
        generate_sample_pdf(sample_inputs[0], crop, months)
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")


def generate_sample_pdf(sample_data: dict, crop: str, months: int):
    """
    Generate a sample PDF report to verify the pipeline
    
    Args:
        sample_data: Dictionary of sensor readings
        crop: Predicted crop name
        months: Predicted growth months
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        
        timestamp = datetime.now()
        file_name = f"sample_report_{timestamp.strftime('%Y%m%d_%H%M%S')}.pdf"
        
        doc = SimpleDocTemplate(file_name, pagesize=A4)
        styles = getSampleStyleSheet()
        
        content = []
        
        # Title
        title_style = ParagraphStyle(
            "Title", parent=styles["Title"],
            alignment=1, textColor=colors.HexColor("#2E7D32")
        )
        content.append(Paragraph("AgriSetu Sample Prediction Report", title_style))
        content.append(Spacer(1, 20))
        
        # Sensor data table
        data = [["Parameter", "Value"]]
        for key, value in sample_data.items():
            data.append([key.replace("_", " "), f"{value:.1f}"])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        content.append(table)
        content.append(Spacer(1, 20))
        
        # Prediction
        content.append(Paragraph(f"Recommended Crop: {crop}", styles["Heading2"]))
        content.append(Paragraph(f"Growth Duration: {months} months", styles["Normal"]))
        
        doc.build(content)
        
        print(f"\n✅ Sample PDF generated: {file_name}")
        
    except ImportError:
        print("\n⚠️ ReportLab not installed. Skipping PDF generation.")
    except Exception as e:
        print(f"\n⚠️ PDF generation failed: {e}")


# ================== MAIN PIPELINE ==================
def main(data_path: Path = None):
    """
    Main training pipeline
    
    Args:
        data_path: Optional custom path to dataset
    """
    print("="*60)
    print("🌱 AGRISETU MODEL TRAINING PIPELINE")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Use provided path or default
    if data_path is None:
        data_path = Config.DATASET_PATH
    
    try:
        # 1. Create directories
        Config.create_directories()
        
        # 2. Load dataset
        df = load_dataset(data_path)
        
        # 3. Validate dataset
        validate_dataset(df)
        
        # 4. Explore dataset
        explore_dataset(df)
        
        # 5. Preprocess data
        X, y_crop, y_months, label_encoder, scaler = preprocess_data(df)
        
        # 6. Train-test split
        print("\n✂️ Splitting data...")
        X_train, X_test, y_crop_train, y_crop_test, y_months_train, y_months_test = train_test_split(
            X, y_crop, y_months, 
            test_size=Config.TEST_SIZE, 
            random_state=Config.RANDOM_STATE,
            stratify=y_crop
        )
        print(f"✅ Training set: {len(X_train)} samples")
        print(f"✅ Testing set: {len(X_test)} samples")
        
        # 7. Train models
        crop_model, crop_metrics = train_crop_model(
            X_train, y_crop_train, X_test, y_crop_test, label_encoder
        )
        
        month_model, month_metrics = train_month_model(
            X_train, y_months_train, X_test, y_months_test
        )
        
        # 8. Create lookup table
        crop_month_lookup = create_crop_month_lookup(df)
        
        # 9. Combine metrics
        all_metrics = {
            'crop_model': crop_metrics,
            'month_model': month_metrics,
            'dataset_size': len(df),
            'train_size': len(X_train),
            'test_size': len(X_test)
        }
        
        # 10. Save models
        save_models(
            crop_model, month_model, label_encoder, scaler,
            crop_month_lookup, all_metrics
        )
        
        # 11. Test saved models
        if test_saved_models():
            print("\n✅ All tests passed!")
        else:
            print("\n⚠️ Some tests failed!")
        
        # 12. Demo prediction
        demo_prediction()
        
        print("\n" + "="*60)
        print("✅ TRAINING COMPLETE!")
        print("="*60)
        print(f"\n📁 Models saved in: {Config.MODELS_DIR.absolute()}")
        print("\n📋 Next Steps:")
        print("   1. Copy the 'models' folder to your AgriSetu WhatsApp bot project")
        print("   2. Deploy the bot on Render.com")
        print("   3. Test with WhatsApp message: 'prediction'")
        
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ================== ENTRY POINT ==================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train AgriSetu ML models")
    parser.add_argument(
        "--data_path", 
        type=Path,
        help="Path to dataset file (Excel or CSV)"
    )
    parser.add_argument(
        "--demo_only",
        action="store_true",
        help="Run demo prediction only (requires existing models)"
    )
    
    args = parser.parse_args()
    
    if args.demo_only:
        if Config.CROP_MODEL_FILE.exists():
            demo_prediction()
        else:
            print("❌ Models not found. Run training first.")
    else:
        main(args.data_path)