<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Insert title here</title>
</head>
<body>

<%
	request.setCharacterEncoding("utf-8");
	String id = request.getParameter("id");
	String pass = request.getParameter("pass");

	session.setAttribute("id", id);
	session.setAttribute("pass", pass);
	
세션유지시간 : session.setMaxInactiveInterval(5);
	%>
	
	<h2>님 환영합니다.</h2>
	<a href="SessionShopping.jsp">solshop</a>
<%-- 세션유지시간 : <%= session.setMaxInactiveInterval(604800) %> 7일 --%>
<%-- 세션유지시간 : <%= session.setMaxInactiveInterval(-1) %> 무제한 --%>

</body>	
</html>