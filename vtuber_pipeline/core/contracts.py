"""Pydantic v2 dataclasses for pipeline stage contracts.

This module defines the data contracts used for communication between
pipeline stages. Each contract tracks the input hash, output path,
stage name, configuration, and status.
"""

from typing import Literal, Dict, Any, Optional
from pydantic import BaseModel, Field


class ImageContract(BaseModel):
    """Base contract for image input stages.
    
    Attributes:
        input_hash: SHA256 hash of the input image.
        output_path: Path to the output file(s).
        stage_name: Name of the pipeline stage.
        config: Stage-specific configuration.
        status: Current status of the stage.
    """
    input_hash: str = Field(..., description="SHA256 hash of the input image")
    output_path: str = Field(..., description="Path to the output file(s)")
    stage_name: str = Field(default="image", description="Name of the pipeline stage")
    config: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific configuration")
    status: Literal['pending', 'running', 'complete', 'failed'] = Field(
        default='pending', 
        description="Current status of the stage"
    )


class FaceLandmarksContract(BaseModel):
    """Contract for face landmark detection stage.
    
    Attributes:
        input_hash: SHA256 hash of the input image.
        output_path: Path to the output JSON file.
        stage_name: Name of the pipeline stage.
        config: Stage-specific configuration.
        status: Current status of the stage.
        bbox: Bounding box of detected face [x1, y1, x2, y2].
        landmarks: List of 28 landmark points [[x, y], ...].
        score: Detection confidence score.
        quality_metrics: Additional quality metrics.
    """
    input_hash: str = Field(..., description="SHA256 hash of the input image")
    output_path: str = Field(..., description="Path to the output JSON file")
    stage_name: str = Field(default="face_landmarks", description="Name of the pipeline stage")
    config: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific configuration")
    status: Literal['pending', 'running', 'complete', 'failed'] = Field(
        default='pending',
        description="Current status of the stage"
    )
    bbox: Optional[list] = Field(default=None, description="Bounding box [x1, y1, x2, y2]")
    landmarks: Optional[list] = Field(default=None, description="List of 28 landmark points")
    score: Optional[float] = Field(default=None, description="Detection confidence score")
    quality_metrics: Dict[str, Any] = Field(default_factory=dict, description="Quality metrics")


class ReferenceContract(BaseModel):
    """Contract for reference reconstruction (TripoSR) stage.
    
    Attributes:
        input_hash: SHA256 hash of the input image.
        output_path: Path to the output mesh file.
        stage_name: Name of the pipeline stage.
        config: Stage-specific configuration.
        status: Current status of the stage.
        mesh_path: Path to the reconstructed mesh.
        texture_path: Path to the texture file.
    """
    input_hash: str = Field(..., description="SHA256 hash of the input image")
    output_path: str = Field(..., description="Path to the output mesh file")
    stage_name: str = Field(default="reference", description="Name of the pipeline stage")
    config: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific configuration")
    status: Literal['pending', 'running', 'complete', 'failed'] = Field(
        default='pending',
        description="Current status of the stage"
    )
    mesh_path: Optional[str] = Field(default=None, description="Path to the reconstructed mesh")
    texture_path: Optional[str] = Field(default=None, description="Path to the texture file")


class FittingContract(BaseModel):
    """Contract for template fitting stage.
    
    Attributes:
        input_hash: SHA256 hash of the input image.
        output_path: Path to the output mesh file.
        stage_name: Name of the pipeline stage.
        config: Stage-specific configuration.
        status: Current status of the stage.
        fit_mesh_path: Path to the fitted mesh.
        deformation_graph_path: Path to the deformation graph (.npz).
        fit_report_path: Path to the fit report JSON.
    """
    input_hash: str = Field(..., description="SHA256 hash of the input image")
    output_path: str = Field(..., description="Path to the output mesh file")
    stage_name: str = Field(default="fitting", description="Name of the pipeline stage")
    config: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific configuration")
    status: Literal['pending', 'running', 'complete', 'failed'] = Field(
        default='pending',
        description="Current status of the stage"
    )
    fit_mesh_path: Optional[str] = Field(default=None, description="Path to the fitted mesh")
    deformation_graph_path: Optional[str] = Field(default=None, description="Path to deformation graph")
    fit_report_path: Optional[str] = Field(default=None, description="Path to fit report JSON")


class RigContract(BaseModel):
    """Contract for rigging stage.
    
    Attributes:
        input_hash: SHA256 hash of the input image.
        output_path: Path to the output rigged mesh file.
        stage_name: Name of the pipeline stage.
        config: Stage-specific configuration.
        status: Current status of the stage.
        rigged_mesh_path: Path to the rigged mesh.
        bone_count: Number of bones in the rig.
        springbone_count: Number of SpringBone configurations.
    """
    input_hash: str = Field(..., description="SHA256 hash of the input image")
    output_path: str = Field(..., description="Path to the output rigged mesh file")
    stage_name: str = Field(default="rig", description="Name of the pipeline stage")
    config: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific configuration")
    status: Literal['pending', 'running', 'complete', 'failed'] = Field(
        default='pending',
        description="Current status of the stage"
    )
    rigged_mesh_path: Optional[str] = Field(default=None, description="Path to the rigged mesh")
    bone_count: Optional[int] = Field(default=None, description="Number of bones")
    springbone_count: Optional[int] = Field(default=0, description="Number of SpringBones")


class ExpressionContract(BaseModel):
    """Contract for expression generation stage.
    
    Attributes:
        input_hash: SHA256 hash of the input image.
        output_path: Path to the output file.
        stage_name: Name of the pipeline stage.
        config: Stage-specific configuration.
        status: Current status of the stage.
        expression_count: Number of expressions generated.
        expressions: Dictionary mapping expression names to morph data.
    """
    input_hash: str = Field(..., description="SHA256 hash of the input image")
    output_path: str = Field(..., description="Path to the output file")
    stage_name: str = Field(default="expression", description="Name of the pipeline stage")
    config: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific configuration")
    status: Literal['pending', 'running', 'complete', 'failed'] = Field(
        default='pending',
        description="Current status of the stage"
    )
    expression_count: Optional[int] = Field(default=0, description="Number of expressions")
    expressions: Dict[str, Any] = Field(default_factory=dict, description="Expression morph data")


class VRMContract(BaseModel):
    """Contract for VRM export stage.
    
    Attributes:
        input_hash: SHA256 hash of the input image.
        output_path: Path to the output VRM file.
        stage_name: Name of the pipeline stage.
        config: Stage-specific configuration.
        status: Current status of the stage.
        vrm_path: Path to the exported VRM file.
        validation_report_path: Path to the validation report JSON.
    """
    input_hash: str = Field(..., description="SHA256 hash of the input image")
    output_path: str = Field(..., description="Path to the output VRM file")
    stage_name: str = Field(default="vrm", description="Name of the pipeline stage")
    config: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific configuration")
    status: Literal['pending', 'running', 'complete', 'failed'] = Field(
        default='pending',
        description="Current status of the stage"
    )
    vrm_path: Optional[str] = Field(default=None, description="Path to the VRM file")
    validation_report_path: Optional[str] = Field(default=None, description="Path to validation report")


class AttachmentContract(BaseModel):
    """Contract for accessory attachment stage.
    
    Attributes:
        input_hash: SHA256 hash of the input image.
        output_path: Path to the output file.
        stage_name: Name of the pipeline stage.
        config: Stage-specific configuration.
        status: Current status of the stage.
        accessory_meshes: List of accessory mesh paths.
        attachment_config_path: Path to the attachment configuration JSON.
    """
    input_hash: str = Field(..., description="SHA256 hash of the input image")
    output_path: str = Field(..., description="Path to the output file")
    stage_name: str = Field(default="attachment", description="Name of the pipeline stage")
    config: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific configuration")
    status: Literal['pending', 'running', 'complete', 'failed'] = Field(
        default='pending',
        description="Current status of the stage"
    )
    accessory_meshes: list = Field(default_factory=list, description="List of accessory mesh paths")
    attachment_config_path: Optional[str] = Field(default=None, description="Path to attachment config")
