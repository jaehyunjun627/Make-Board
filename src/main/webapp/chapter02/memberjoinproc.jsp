<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<%@page import="model.MemDTO"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>memberjoinproc</title>
</head>
<body>
	<center>

		<h2>Member Info</h2>
		<%
		request.setCharacterEncoding("utf-8");
		%>
		<jsp:useBean class="model.MemDTO" id="mdto">

			<jsp:setProperty name="mdto" property="*" />


		</jsp:useBean>

		<h2>
			ID :
			<jsp:getProperty name="mdto" property="id" />
		</h2>

		<h2>
			Email:
			<jsp:getProperty name="mdto" property="email" />
		</h2>

		<h2>
			Phone:
			<jsp:getProperty name="mdto" property="tel" />
		</h2>

		<h2>
			Address:
			<%-- <jsp:getProperty name="mdto" property="address"/> --%>
			<%=mdto.getAddress()%>
		</h2>
	</center>

</body>
</html>