<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>Insert title here</title>
</head>
<body>
<div align="center"> 
<h2>application</h2>
username 값
<%= application.getAttribute("username") %> <br />

<%
Integer count = (Integer) application.getAttribute("count");

int cnt = count.intValue() +1;
application.setAttribute("count",cnt);
%>

count :
<%=cnt %>
</div>
</body>
</html>