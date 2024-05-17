from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple
from postgrest.base_request_builder import APIResponse

class BaseSQLDatabase(ABC):

  @abstractmethod
  def getAllMaterialsForCourse(self, course_name: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getMaterialsForCourseAndS3Path(self, course_name: str, s3_path: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getMaterialsForCourseAndKeyAndValue(self, course_name: str, key: str, value: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def deleteMaterialsForCourseAndKeyAndValue(self, course_name: str, key: str, value: str):
    pass
  @abstractmethod
  def deleteMaterialsForCourseAndS3Path(self, course_name: str, s3_path: str):
    pass
  @abstractmethod
  def getProjectsMapForCourse(self, course_name: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getDocumentsBetweenDates(self, course_name: str, from_date: str, to_date: str, table_name: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getAllFromTableForDownloadType(self, course_name: str, download_type: str, first_id: int) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getAllConversationsBetweenIds(self, course_name: str, first_id: int, last_id: int, limit: int = 50) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getDocsForIdsGte(self, course_name: str, first_id: int, fields: str = "*", limit: int = 100) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def insertProjectInfo(self, project_info) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getAllFromLLMConvoMonitor(self, course_name: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getCountFromLLMConvoMonitor(self, course_name: str, last_id: int) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getDocMapFromProjects(self, course_name: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getConvoMapFromProjects(self, course_name: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def updateProjects(self, course_name: str, data: dict) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getLatestWorkflowId(self) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def lockWorkflow(self, id: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def deleteLatestWorkflowId(self, id: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def unlockWorkflow(self, id: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass
  @abstractmethod
  def getConversation(self, course_name: str, key: str, value: str) -> APIResponse[Tuple[Dict[str, Any], int]]:
    pass