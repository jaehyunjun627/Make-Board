<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core"%>
<%@ taglib prefix="fmt" uri="http://java.sun.com/jsp/jstl/fmt"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>Insert title here</title>
</head>
<body bgcolor="white">

<h3>&lt; c:forTokens&gt;</h3>
<c:forTokens var="sol" items="솔데스크, 0212314, asdasd" delims=",">
${sol }   <br />

</c:forTokens>
<hr />

<fmt:formatNumber value="3.1423" pattern = "#.00"/>
<% java.util.Date now=new java.util.Date();
	  pageContext.setAttribute("currentDate", now);
	%>
	
<fmt:formatDate value="${currentDate }" pattern="yyyy-MM-dd HH:mm:ss"/>
	
	<hr />
	<center>
		<h3>import:https://www.daum.net/</h3>
	</center>
	<c:import var="myurl" url="https://www.daum.net/"  />
	<c:out value="${myurl }" escapeXml="false" />
	
	
<p></p>
</body>
</html>