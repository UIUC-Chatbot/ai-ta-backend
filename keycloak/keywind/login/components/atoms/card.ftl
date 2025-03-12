<#macro kw content="" footer="" header="">
  <div class="bg-white p-8 rounded-lg flex flex-col gap-6 w-full">
    <#if header?has_content>
      <div class="w-full">
        ${header}
      </div>
    </#if>
    <#if content?has_content>
      <div class="w-full flex flex-col gap-4">
        ${content}
      </div>
    </#if>
    <#if footer?has_content>
      <div class="w-full">
        ${footer} 
      </div>
    </#if>
  </div>
</#macro>