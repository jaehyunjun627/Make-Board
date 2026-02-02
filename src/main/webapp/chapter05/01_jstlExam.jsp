<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>Insert title here</title>
</head>
<body bgcolor="white">
	<h3>&lt;c:remove&gt;</h3>
	<hr />
	<!-- java code: var msg="free" -->

	<c:set var="msg" value="free" />

	before msg: ${msg }
	<br />
	<c:remove var="msg" />
	after msg: ${msg }
	<p></p>
	<c:catch var="errMsg">
		<%=9 / 0%>
	</c:catch>
	ERROR Message: ${errMsg}
	<p></p>
	<hr />

	<h3>&lt;c:if&gt;</h3>
	<c:set var="ifMsg" value="user1" />
	ifMsg: ${ifMsg }
	<br />
	<c:if test="${ifMsg=='user1' }">
	result: ${result }
	</c:if>
	<p></p>

	<br />

	<!-- c:choose 태그 -->
	<h3>&lt;c:choose&gt;</h3>
	<c:set var="age" value="24" />
	<c:choose>
		<c:when test="${age>=20 }">
			<p>성인입니다</p>
		</c:when>
		<c:otherwise>
			<p>미성년자 입니다</p>
		</c:otherwise>
	</c:choose>
	<p></p>

	<c:set var="role" value="admin" />
	<c:choose>
		<c:when test="${role=='admin' }">
			<p>Welcome, Admin! You have full access</p>
		</c:when>
		<c:when test="${role=='user' }">
			<p>Welcome, User! You have limited access</p>
		</c:when>
		<c:otherwise>
			<p>Unknown role, access denied</p>
		</c:otherwise>
	</c:choose>
	<hr />
	
	<p></p>
	
	<!-- c:forEach 태그  / 자바: for(int i=1;i<=5; i++)-->
	
	<c:forEach var="i" begin="1" end="5">
	<p>번호: ${i }</p>
	</c:forEach>
	
	
	

</body>
</html>